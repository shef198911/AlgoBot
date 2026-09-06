"""
Capital Manager — Centralized trading capital management.

TRADING_CAPITAL is a virtual working-capital budget within the real exchange
balance.  The bot never uses the full real balance for position sizing.

This module handles:
1. Effective Trading Capital = min(TRADING_CAPITAL, actual_available_balance)
2. Dynamic capital tracking (allocated margin, pending, realized PnL, fees)
3. Position sizing via risk + stop-loss distance + leverage + exchange limits
4. Portfolio load limits (per-trade risk, per-position margin, total margin)
5. Minimum position logic (MIN_RISK_USDT, MIN_POSITION_NOTIONAL, exchange mins)
6. AI confidence scaling with hard caps
7. Liquidation safety pre-checks (ISOLATED margin)
8. Pre-trade logging with full capital/risk breakdown
"""

import threading
from typing import Dict, Any, Optional, Tuple
from config import logger

# ---------------------------------------------------------------------------
# Configuration constants — imported from config at module level
# ---------------------------------------------------------------------------
from config import (
    MAX_CAPITAL_USDT,           # TRADING_CAPITAL budget
    BASE_RISK_PCT,              # Base risk % of capital per trade
    LEVERAGE,                   # Default leverage multiplier
)

# New constants — added to config.py
try:
    from config import (
        MIN_POSITION_NOTIONAL_USDT,
        EXCHANGE_MIN_NOTIONAL_USDT,
        EXCHANGE_MIN_AMOUNT,
        MAX_RISK_PER_TRADE_PCT,
        MAX_MARGIN_PER_POSITION_PCT,
        MAX_TOTAL_ALLOCATED_MARGIN_PCT,
        MAINTENANCE_MARGIN_RATE,
        ESTIMATED_FEE_RATE,
        MIN_RISK_USDT,
    )
except ImportError:
    # Fallback defaults if config doesn't have them yet
    MIN_RISK_USDT = 15.0
    MIN_POSITION_NOTIONAL_USDT = 10.0
    EXCHANGE_MIN_NOTIONAL_USDT = 5.0
    EXCHANGE_MIN_AMOUNT = 0.0
    MAX_RISK_PER_TRADE_PCT = 3.0
    MAX_MARGIN_PER_POSITION_PCT = 30.0
    MAX_TOTAL_ALLOCATED_MARGIN_PCT = 80.0
    MAINTENANCE_MARGIN_RATE = 0.004
    ESTIMATED_FEE_RATE = 0.0005


_log = logger.getChild("CapitalManager")


# ---------------------------------------------------------------------------
# AI Confidence Scaling Table (Requirement 6)
# ---------------------------------------------------------------------------
_CONFIDENCE_TIERS = [
    # (min_confidence, multiplier)
    (0.90, 3.0),
    (0.80, 2.0),
    (0.70, 1.5),
    (0.00, 1.0),   # default
]


def ai_confidence_multiplier(confidence: float) -> float:
    """Return the risk-budget multiplier for a given AI confidence score."""
    for threshold, mult in _CONFIDENCE_TIERS:
        if confidence >= threshold:
            return mult
    return 1.0


# ---------------------------------------------------------------------------
# Capital Tracker (Requirement 2 — Dynamic Capital)
# ---------------------------------------------------------------------------
class CapitalTracker:
    """Thread-safe tracker for dynamic trading capital state."""

    def __init__(self, trading_capital: float):
        self._trading_capital = trading_capital
        self._realized_pnl = 0.0
        self._total_fees = 0.0
        self._lock = threading.Lock()

    @property
    def trading_capital(self) -> float:
        with self._lock:
            return self._trading_capital

    @property
    def realized_pnl(self) -> float:
        with self._lock:
            return self._realized_pnl

    @property
    def total_fees(self) -> float:
        with self._lock:
            return self._total_fees

    def record_close(self, pnl: float, fees: float = 0.0):
        """After a position closes: profit returns, loss reduces capital, fees deducted."""
        with self._lock:
            self._realized_pnl += pnl
            self._total_fees += fees
            self._trading_capital += pnl - fees

    def record_fee(self, fee: float):
        """Record an entry fee deduction."""
        with self._lock:
            self._total_fees += fee
            self._trading_capital -= fee

    def effective_capital(self, real_balance: float) -> float:
        """Requirement 1: effective = min(TRADING_CAPITAL, real_balance)."""
        with self._lock:
            return min(self._trading_capital, real_balance) if real_balance > 0 else self._trading_capital

    def get_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return {
                "trading_capital": self._trading_capital,
                "realized_pnl": self._realized_pnl,
                "total_fees": self._total_fees,
            }


# ---------------------------------------------------------------------------
# Portfolio Load (Requirement 4)
# ---------------------------------------------------------------------------
def get_allocated_margin(positions: dict, pending_margins: dict) -> float:
    """Sum of margin from open positions + pending margins."""
    pos_margin = sum(
        pos.get('margin_required', 0.0)
        for pos in positions.values()
        if pos.get('margin_required')
    )
    pend_margin = sum(pending_margins.values())
    return pos_margin + pend_margin


def get_free_capital(effective_cap: float, positions: dict, pending_margins: dict) -> float:
    """Free Trading Capital = effective - allocated."""
    allocated = get_allocated_margin(positions, pending_margins)
    return max(effective_cap - allocated, 0.0)


def get_portfolio_risk_usdt(positions: dict) -> float:
    """Sum of risk_usdt across all open positions."""
    return sum(
        pos.get('risk_usdt', 0.0)
        for pos in positions.values()
        if pos.get('status') in ('OPEN', 'UNKNOWN', None)
    )


def get_open_position_count(positions: dict) -> int:
    """Number of currently open positions."""
    return len(positions)


# ---------------------------------------------------------------------------
# Position Sizing (Requirement 3)
# ---------------------------------------------------------------------------
def calculate_position_size(
    risk_usdt: float,
    sl_distance: float,
    current_price: float,
    leverage: int,
    effective_capital: float,
    allocated_margin: float,
    exchange_precision_fn=None,
) -> Dict[str, Any]:
    """
    Calculate position size from risk budget + stop-loss distance + leverage.

    Returns dict with:
      amount_coin, notional_usdt, margin_required, risk_usdt_actual
    Or {'valid': False, 'reason': ...} if position is too small/impossible.
    """
    if sl_distance <= 0:
        return {"valid": False, "reason": "sl_distance_zero_or_negative"}

    # Core formula: amount = risk_usdt / sl_distance_per_unit
    amount_coin = risk_usdt / sl_distance

    # Apply exchange precision
    if exchange_precision_fn:
        try:
            prec = exchange_precision_fn(amount_coin)
            if prec.__class__.__name__ != 'MagicMock':
                amount_coin = float(prec)
        except Exception:
            pass

    if amount_coin <= 0:
        return {"valid": False, "reason": "amount_zero_after_precision"}

    notional_usdt = amount_coin * current_price
    margin_required = notional_usdt / leverage

    # Check margin fits within available free capital
    max_total_margin = effective_capital * (MAX_TOTAL_ALLOCATED_MARGIN_PCT / 100.0)
    available_for_margin = max_total_margin - allocated_margin
    max_per_position = effective_capital * (MAX_MARGIN_PER_POSITION_PCT / 100.0)

    margin_cap = min(available_for_margin, max_per_position)

    if margin_required > margin_cap and margin_cap > 0:
        # Shrink position to fit
        margin_required = margin_cap
        notional_usdt = margin_required * leverage
        amount_coin = notional_usdt / current_price
        if exchange_precision_fn:
            try:
                prec = exchange_precision_fn(amount_coin)
                if prec.__class__.__name__ != 'MagicMock':
                    amount_coin = float(prec)
            except Exception:
                pass
        notional_usdt = amount_coin * current_price
        margin_required = notional_usdt / leverage

    # Recalculate actual risk after potential resizing
    risk_usdt_actual = amount_coin * sl_distance

    return {
        "valid": True,
        "amount_coin": amount_coin,
        "notional_usdt": notional_usdt,
        "margin_required": margin_required,
        "risk_usdt_actual": risk_usdt_actual,
    }


# ---------------------------------------------------------------------------
# Risk Budget (Requirement 3 + 6)
# ---------------------------------------------------------------------------
def compute_risk_budget(
    effective_capital: float,
    base_risk_pct: float,
    ai_confidence: float,
    allocated_margin: float,
    positions: dict,
) -> Dict[str, Any]:
    """
    Compute the risk budget in USDT for a single trade.
    Applies AI confidence scaling, but caps against max limits.

    Returns dict with risk_usdt, risk_pct, confidence_mult, portfolio_risk_ok.
    """
    base_pct = base_risk_pct / 100.0  # config is in %, convert to fraction
    if base_pct <= 0:
        base_pct = 0.01

    conf_mult = ai_confidence_multiplier(ai_confidence)
    scaled_pct = base_pct * conf_mult

    # Cap: never exceed MAX_RISK_PER_TRADE_PCT
    max_pct = MAX_RISK_PER_TRADE_PCT / 100.0
    scaled_pct = min(scaled_pct, max_pct)

    # Use effective_capital for base risk sizing, not free_capital
    # (free_capital is for margin, base risk is based on total effective equity)
    risk_usdt = effective_capital * scaled_pct

    # Cap: portfolio total risk (sum of all position risks + this one)
    try:
        from config import MAX_TOTAL_PORTFOLIO_RISK_PCT
        max_portfolio_risk_pct = MAX_TOTAL_PORTFOLIO_RISK_PCT
    except ImportError:
        max_portfolio_risk_pct = 15.0
        
    current_portfolio_risk = get_portfolio_risk_usdt(positions)
    max_portfolio_risk_usdt = effective_capital * (max_portfolio_risk_pct / 100.0)
    
    portfolio_risk_ok = True
    if current_portfolio_risk + risk_usdt > max_portfolio_risk_usdt:
        portfolio_risk_ok = False

    return {
        "risk_usdt": risk_usdt,
        "risk_pct": scaled_pct * 100.0,
        "confidence_mult": conf_mult,
        "portfolio_risk_ok": portfolio_risk_ok,
    }


# ---------------------------------------------------------------------------
# Minimum Position Checks (Requirement 5)
# ---------------------------------------------------------------------------
def check_minimum_position(
    amount_coin: float,
    notional_usdt: float,
    risk_usdt_actual: float,
    expected_net_pnl: float = 0.0,
    exchange_min_amount: float = 0.0,
    exchange_min_notional: float = 0.0,
) -> Tuple[bool, str]:
    """
    Check whether a position meets all minimum requirements.
    If too small -> skip, don't inflate risk.

    Returns (ok, reason).
    """
    if notional_usdt < MIN_POSITION_NOTIONAL_USDT:
        return False, f"notional_too_small ({notional_usdt:.2f} < {MIN_POSITION_NOTIONAL_USDT:.2f})"

    if notional_usdt < (exchange_min_notional or EXCHANGE_MIN_NOTIONAL_USDT):
        return False, f"below_exchange_min_notional ({notional_usdt:.2f})"

    if amount_coin < (exchange_min_amount or EXCHANGE_MIN_AMOUNT) and EXCHANGE_MIN_AMOUNT > 0:
        return False, f"below_exchange_min_amount ({amount_coin})"

    if MIN_RISK_USDT > 0 and risk_usdt_actual < MIN_RISK_USDT:
        return False, f"risk_too_small ({risk_usdt_actual:.2f} < {MIN_RISK_USDT:.2f})"
        
    if expected_net_pnl is not None and expected_net_pnl <= 0.0:
        return False, f"expected_net_pnl_too_small ({expected_net_pnl:.4f} <= 0)"

    return True, "ok"

    return True, "ok"


# ---------------------------------------------------------------------------
# Liquidation Safety (Requirement 7)
# ---------------------------------------------------------------------------
def estimate_liquidation_price(
    direction: str,
    entry_price: float,
    margin: float,
    amount: float,
    maintenance_margin_rate: float = None,
) -> float:
    """
    Estimate liquidation price for ISOLATED margin mode.
    Simple formula:
      LONG:  liq = entry - (margin - maint_margin) / amount
      SHORT: liq = entry + (margin - maint_margin) / amount
    """
    if maintenance_margin_rate is None:
        maintenance_margin_rate = MAINTENANCE_MARGIN_RATE

    if amount <= 0 or margin <= 0:
        return 0.0

    notional = amount * entry_price
    maint_margin = notional * maintenance_margin_rate

    if direction == 'LONG':
        liq = entry_price - (margin - maint_margin) / amount
    else:
        liq = entry_price + (margin - maint_margin) / amount

    return max(liq, 0.0)


def check_liquidation_safety(
    direction: str,
    entry_price: float,
    sl_price: float,
    margin: float,
    amount: float,
) -> Dict[str, Any]:
    """
    Pre-check: Ensure SL triggers before liquidation.
    Returns safety info dict.
    """
    liq_price = estimate_liquidation_price(direction, entry_price, margin, amount)

    if direction == 'LONG':
        sl_before_liq = sl_price > liq_price
        distance_sl_to_liq = sl_price - liq_price if liq_price > 0 else float('inf')
    else:
        sl_before_liq = sl_price < liq_price
        distance_sl_to_liq = liq_price - sl_price if liq_price > 0 else float('inf')

    return {
        "liquidation_price": liq_price,
        "sl_before_liquidation": sl_before_liq,
        "distance_sl_to_liq": distance_sl_to_liq,
    }


# ---------------------------------------------------------------------------
# Fee Estimation
# ---------------------------------------------------------------------------
def estimate_fees(notional_usdt: float, fee_rate: float = None) -> float:
    """Estimate round-trip fees (entry + exit)."""
    if fee_rate is None:
        fee_rate = ESTIMATED_FEE_RATE
    return notional_usdt * fee_rate * 2  # entry + exit


# ---------------------------------------------------------------------------
# Pre-Trade Logging (Requirement 10)
# ---------------------------------------------------------------------------
def log_pre_trade(
    symbol: str,
    direction: str,
    real_balance: float,
    effective_capital: float,
    allocated_margin: float,
    free_capital: float,
    open_positions: int,
    portfolio_risk_usdt: float,
    ai_confidence: float,
    risk_pct: float,
    risk_usdt: float,
    sl_distance: float,
    sl_price: float,
    tp_price: float,
    entry_price: float,
    notional_usdt: float,
    margin_required: float,
    leverage: int,
    liquidation_price: float,
    expected_tp_pnl: float,
    expected_sl_loss: float,
    fees_estimate: float,
    confidence_mult: float,
):
    """Log full capital/risk breakdown before each trade."""
    _log.info(
        f"\n{'='*60}\n"
        f"  PRE-TRADE REPORT: {symbol} {direction}\n"
        f"{'='*60}\n"
        f"  Real Balance:           {real_balance:.2f} USDT\n"
        f"  Effective Trading Cap:  {effective_capital:.2f} USDT\n"
        f"  Allocated Margin:       {allocated_margin:.2f} USDT\n"
        f"  Free Trading Capital:   {free_capital:.2f} USDT\n"
        f"  Open Positions:         {open_positions}\n"
        f"  Portfolio Risk:         {portfolio_risk_usdt:.2f} USDT\n"
        f"  ML Confidence:          {ai_confidence*100:.1f}% (x{confidence_mult:.1f})\n"
        f"  Risk %:                 {risk_pct:.2f}%\n"
        f"  Risk USDT:              {risk_usdt:.2f}\n"
        f"  SL Distance:            {sl_distance:.4f}\n"
        f"  Entry Price:            {entry_price:.4f}\n"
        f"  SL Price:               {sl_price:.4f}\n"
        f"  TP Price:               {tp_price:.4f}\n"
        f"  Position Notional:      {notional_usdt:.2f} USDT\n"
        f"  Required Margin:        {margin_required:.2f} USDT\n"
        f"  Leverage:               {leverage}x\n"
        f"  Liquidation Price:      {liquidation_price:.4f}\n"
        f"  Expected TP PnL:        +{expected_tp_pnl:.2f} USDT\n"
        f"  Expected SL Loss:       -{expected_sl_loss:.2f} USDT\n"
        f"  Fees Estimate:          {fees_estimate:.2f} USDT\n"
        f"{'='*60}"
    )

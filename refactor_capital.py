import re

with open('G:/AlgoBot/capital_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace get_portfolio_risk_usdt
old_get_portfolio = """def get_portfolio_risk_usdt(positions: dict) -> float:
    \"\"\"Sum of risk_usdt across all open positions.\"\"\"
    return sum(pos.get('risk_usdt', 0.0) for pos in positions.values() if pos.get('status') in ('OPEN', 'UNKNOWN', None))"""

new_get_portfolio = """def get_portfolio_risk_usdt(positions: dict) -> float:
    \"\"\"
    Sum ONLY actual risk of open positions.
    New state uses risk_usdt_actual.
    Legacy state may contain risk_usdt and is accepted only
    for backward compatibility.
    \"\"\"
    total = 0.0

    for pos in positions.values():
        if pos.get('status') not in ('OPEN', 'UNKNOWN', None):
            continue

        actual_risk = pos.get('risk_usdt_actual')

        if actual_risk is None:
            # Legacy state compatibility only.
            actual_risk = pos.get('risk_usdt', 0.0)

        try:
            actual_risk = float(actual_risk)
        except (TypeError, ValueError):
            actual_risk = 0.0

        if actual_risk > 0:
            total += actual_risk

    return total"""

if old_get_portfolio in content:
    content = content.replace(old_get_portfolio, new_get_portfolio)
else:
    # try regex
    pattern = re.compile(r'def get_portfolio_risk_usdt\(positions: dict\) -> float:.*?return sum\(pos\.get\(\'risk_usdt\', 0\.0\).*?\)', re.DOTALL)
    content = re.sub(pattern, new_get_portfolio, content)

# Replace calculate_position_size
old_calc_pos = re.compile(r'def calculate_position_size\([\s\S]*?return \{\n        "valid": True,\n        "amount_coin": amount_coin,\n        "notional_usdt": notional_usdt,\n        "margin_required": margin_required,\n        "risk_usdt_actual": risk_usdt_actual,\n    \}', re.DOTALL)

new_calc_pos = """def calculate_position_size(
    risk_usdt: float,
    sl_distance: float,
    current_price: float,
    leverage: int,
    effective_capital: float,
    allocated_margin: float,
    exchange_precision_fn=None,
) -> dict:

    if risk_usdt <= 0:
        return {
            "valid": False,
            "reason": "risk_usdt_zero_or_negative"
        }

    if sl_distance <= 0:
        return {
            "valid": False,
            "reason": "sl_distance_zero_or_negative"
        }

    if current_price <= 0:
        return {
            "valid": False,
            "reason": "current_price_zero_or_negative"
        }

    if leverage <= 0:
        return {
            "valid": False,
            "reason": "invalid_leverage"
        }

    from config import MAX_RISK_PER_TRADE_PCT
    max_trade_risk = (
        effective_capital
        * MAX_RISK_PER_TRADE_PCT
        / 100.0
    )

    requested_risk = min(
        float(risk_usdt),
        float(max_trade_risk)
    )

    amount_coin = requested_risk / sl_distance

    # Exchange precision
    if exchange_precision_fn:
        try:
            amount_coin = float(
                exchange_precision_fn(amount_coin)
            )
        except Exception as e:
            return {
                "valid": False,
                "reason": f"amount_precision_failed: {e}"
            }

    if amount_coin <= 0:
        return {
            "valid": False,
            "reason": "amount_zero_after_precision"
        }

    notional_usdt = (
        amount_coin * current_price
    )

    margin_required = (
        notional_usdt / leverage
    )

    max_total_margin = (
        effective_capital
        * MAX_TOTAL_ALLOCATED_MARGIN_PCT
        / 100.0
    )

    max_position_margin = (
        effective_capital
        * MAX_MARGIN_PER_POSITION_PCT
        / 100.0
    )

    available_margin = max(
        max_total_margin - allocated_margin,
        0.0
    )

    margin_cap = min(
        max_position_margin,
        available_margin
    )

    if margin_cap <= 0:
        return {
            "valid": False,
            "reason": "no_margin_capacity"
        }

    if margin_required > margin_cap:

        margin_required = margin_cap

        notional_usdt = (
            margin_required * leverage
        )

        amount_coin = (
            notional_usdt / current_price
        )

        if exchange_precision_fn:
            try:
                amount_coin = float(
                    exchange_precision_fn(amount_coin)
                )
            except Exception as e:
                return {
                    "valid": False,
                    "reason": f"amount_precision_failed_after_shrink: {e}"
                }

        if amount_coin <= 0:
            return {
                "valid": False,
                "reason": "amount_zero_after_margin_shrink"
            }

        notional_usdt = (
            amount_coin * current_price
        )

        margin_required = (
            notional_usdt / leverage
        )

    risk_usdt_actual = (
        amount_coin * sl_distance
    )

    # Final hard checks
    if risk_usdt_actual > requested_risk + 1e-8:
        return {
            "valid": False,
            "reason": "actual_risk_exceeds_requested_risk",
            "risk_usdt_actual": risk_usdt_actual,
            "risk_usdt_requested": requested_risk,
        }

    if margin_required > max_position_margin + 1e-8:
        return {
            "valid": False,
            "reason": "position_margin_limit_exceeded"
        }

    if (
        allocated_margin + margin_required
        > max_total_margin + 1e-8
    ):
        return {
            "valid": False,
            "reason": "total_margin_limit_exceeded"
        }

    return {
        "valid": True,
        "amount_coin": float(amount_coin),
        "notional_usdt": float(notional_usdt),
        "margin_required": float(margin_required),
        "risk_usdt_actual": float(risk_usdt_actual),
        "risk_usdt_requested": float(requested_risk),
    }"""

content = re.sub(old_calc_pos, new_calc_pos, content)

# Now CapitalTracker.record_fee
old_record_fee = """    def record_fee(self, fee: float):
        \"\"\"Record an entry fee deduction.\"\"\"
        with self._lock:
            self._total_fees += fee
            self._trading_capital -= fee
            self._save_state_unlocked()"""

new_record_fee = """    def record_fee(
        self,
        fee: float,
        event_id: str = None
    ):
        \"\"\"
        Record a fee exactly once.
        \"\"\"

        with self._lock:

            if event_id and event_id in self.processed_events:
                return

            fee = float(fee)

            if fee < 0:
                raise ValueError(
                    "fee cannot be negative"
                )

            self._total_fees += fee

            self._trading_capital -= fee

            if event_id:
                self.processed_events.add(
                    event_id
                )

            self._save_state_unlocked()"""

content = content.replace(old_record_fee, new_record_fee)

with open('G:/AlgoBot/capital_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated capital_manager.py")

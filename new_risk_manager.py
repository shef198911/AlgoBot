import numpy as np
from typing import Dict, Optional, Any
from config import SL_ATR_BUFFER, MIN_SL_ATR, MAX_SL_ATR, MIN_RR, TP_BUFFER_ATR, logger

_log = logger.getChild("RiskEngine")

class StructureRiskEngine:
    def __init__(self):
        pass

    def _select_invalidation_long(self, setup_type: str, ctx: Dict[str, Any], entry: float, atr: float) -> tuple:
        invalidation_level = None
        reason = ""

        if setup_type == 'BREAKOUT_RETEST':
            broken_level = ctx.get('broken_level')
            swing_low = ctx.get('swing_low')
            levels = []
            if broken_level is not None:
                levels.append((broken_level, "below_retest_support"))
            if swing_low is not None:
                levels.append((swing_low, "below_swing_low"))
            if levels:
                # For LONG breakout retest, we want the highest structural invalidation point (closest to entry)
                best = max(levels, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'SUPPORT_BOUNCE':
            sup = ctx.get('nearest_support')
            swing_low = ctx.get('swing_low')
            candidates = []
            if sup is not None:
                candidates.append((sup, "below_support_zone"))
            if swing_low is not None:
                candidates.append((swing_low, "below_swing_low"))
            if candidates:
                # For LONG: pick the HIGHEST (closest to entry) level
                best = max(candidates, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'TREND_PULLBACK':
            sup = ctx.get('nearest_support')
            swing_low = ctx.get('swing_low')
            candidates = []
            if sup is not None:
                candidates.append((sup, "below_pullback_support"))
            if swing_low is not None:
                candidates.append((swing_low, "below_swing_low"))
            if candidates:
                best = max(candidates, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'LIQUIDITY_SWEEP_LONG':
            sweep_low = ctx.get('sweep_low')
            if sweep_low is not None:
                invalidation_level = sweep_low
                reason = "below_sweep_low"

        if invalidation_level is None:
            sup = ctx.get('nearest_support')
            swing_low = ctx.get('swing_low')
            if sup and swing_low:
                invalidation_level = max(sup, swing_low)
                reason = "below_nearest_support_or_swing_low"
            elif sup:
                invalidation_level = sup
                reason = "below_nearest_support"
            elif swing_low:
                invalidation_level = swing_low
                reason = "below_swing_low"
            else:
                invalidation_level = entry - (atr * 2.0)
                reason = "fallback_atr"

        return invalidation_level, reason

    def _select_invalidation_short(self, setup_type: str, ctx: Dict[str, Any], entry: float, atr: float) -> tuple:
        invalidation_level = None
        reason = ""

        if setup_type == 'BREAKDOWN_RETEST':
            broken_level = ctx.get('broken_level')
            swing_high = ctx.get('swing_high')
            levels = []
            if broken_level is not None:
                levels.append((broken_level, "above_retest_resistance"))
            if swing_high is not None:
                levels.append((swing_high, "above_swing_high"))
            if levels:
                # For SHORT breakout retest, we want the lowest invalidation point (closest to entry)
                best = min(levels, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'RESISTANCE_REJECTION':
            res = ctx.get('nearest_resistance')
            swing_high = ctx.get('swing_high')
            rej_high = ctx.get('rejection_high')
            candidates = []
            if res is not None:
                candidates.append((res, "above_resistance"))
            if swing_high is not None:
                candidates.append((swing_high, "above_swing_high"))
            if rej_high is not None:
                candidates.append((rej_high, "above_rejection_high"))
            if candidates:
                # For SHORT: pick the LOWEST (closest to entry) level
                best = min(candidates, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'TREND_PULLBACK':
            res = ctx.get('nearest_resistance')
            swing_high = ctx.get('swing_high')
            candidates = []
            if res is not None:
                candidates.append((res, "above_pullback_resistance"))
            if swing_high is not None:
                candidates.append((swing_high, "above_swing_high"))
            if candidates:
                best = min(candidates, key=lambda x: x[0])
                invalidation_level = best[0]
                reason = best[1]

        elif setup_type == 'LIQUIDITY_SWEEP_SHORT':
            sweep_high = ctx.get('sweep_high')
            if sweep_high is not None:
                invalidation_level = sweep_high
                reason = "above_sweep_high"

        if invalidation_level is None:
            res = ctx.get('nearest_resistance')
            swing_high = ctx.get('swing_high')
            if res and swing_high:
                invalidation_level = min(res, swing_high)
                reason = "above_nearest_resistance_or_swing_high"
            elif res:
                invalidation_level = res
                reason = "above_nearest_resistance"
            elif swing_high:
                invalidation_level = swing_high
                reason = "above_swing_high"
            else:
                invalidation_level = entry + (atr * 2.0)
                reason = "fallback_atr"

        return invalidation_level, reason

    def calculate_stop_loss(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float) -> Dict[str, Any]:
        """
        Calculate structure-based stop loss.
        """
        if direction == 'LONG':
            invalidation_level, reason = self._select_invalidation_long(setup_type, ctx, entry, atr)
            sl = invalidation_level - (atr * SL_ATR_BUFFER)
            risk_distance = entry - sl

            if risk_distance < atr * MIN_SL_ATR:
                swing_low = ctx.get('swing_low')
                if swing_low and swing_low < invalidation_level:
                    invalidation_level = swing_low
                    sl = invalidation_level - (atr * SL_ATR_BUFFER)
                    reason = "expanded_to_swing_low"

            return {
                "stop_loss": sl,
                "structural_level": invalidation_level,
                "buffer": atr * SL_ATR_BUFFER,
                "reason": reason
            }

        elif direction == 'SHORT':
            invalidation_level, reason = self._select_invalidation_short(setup_type, ctx, entry, atr)
            sl = invalidation_level + (atr * SL_ATR_BUFFER)
            risk_distance = sl - entry

            if risk_distance < atr * MIN_SL_ATR:
                swing_high = ctx.get('swing_high')
                if swing_high and swing_high > invalidation_level:
                    invalidation_level = swing_high
                    sl = invalidation_level + (atr * SL_ATR_BUFFER)
                    reason = "expanded_to_swing_high"

            return {
                "stop_loss": sl,
                "structural_level": invalidation_level,
                "buffer": atr * SL_ATR_BUFFER,
                "reason": reason
            }

        return {}

    def calculate_targets(self, direction: str, entry: float, sl: float, setup_type: str, ctx: Dict[str, Any], atr: float) -> Dict[str, Any]:
        tp1 = None
        tp2 = None
        reason = ""

        if direction == 'LONG':
            res = ctx.get('nearest_resistance')
            swing_high = ctx.get('swing_high')
            targets = []
            if res and res > entry:
                targets.append((res, "nearest_resistance"))
            if swing_high and swing_high > entry:
                targets.append((swing_high, "swing_high"))
            
            if targets:
                targets.sort(key=lambda x: x[0])
                tp1_level = targets[0][0]
                tp1 = tp1_level - (atr * TP_BUFFER_ATR)
                reason = targets[0][1]
                if len(targets) > 1 and targets[1][0] > tp1_level:
                    tp2 = targets[1][0] - (atr * TP_BUFFER_ATR)
            else:
                risk = abs(entry - sl)
                tp1 = entry + risk * MIN_RR
                reason = "fallback_rr"
                
        elif direction == 'SHORT':
            sup = ctx.get('nearest_support')
            swing_low = ctx.get('swing_low')
            targets = []
            if sup and sup < entry:
                targets.append((sup, "nearest_support"))
            if swing_low and swing_low < entry:
                targets.append((swing_low, "swing_low"))
                
            if targets:
                targets.sort(key=lambda x: x[0], reverse=True)
                tp1_level = targets[0][0]
                tp1 = tp1_level + (atr * TP_BUFFER_ATR)
                reason = targets[0][1]
                if len(targets) > 1 and targets[1][0] < tp1_level:
                    tp2 = targets[1][0] + (atr * TP_BUFFER_ATR)
            else:
                risk = abs(entry - sl)
                tp1 = entry - risk * MIN_RR
                reason = "fallback_rr"

        return {
            "tp1": tp1,
            "tp2": tp2,
            "reason": reason
        }

    def calculate_rr(self, direction: str, entry: float, stop_loss: float, target: float) -> float:
        if direction == 'LONG':
            risk = entry - stop_loss
            reward = target - entry
        else:
            risk = stop_loss - entry
            reward = entry - target
            
        if risk <= 0 or reward <= 0:
            return 0.0
        return reward / risk

    def _log_risk_plan(self, symbol: str, direction: str, setup_type: str, entry: float,
                       atr: float, sl_info: Dict, tp_info: Dict, risk_distance: float,
                       rr: float, reject_reason: str):
        sl = sl_info.get('stop_loss', 0)
        structural_level = sl_info.get('structural_level', 0)
        sl_atr_ratio = risk_distance / atr if atr > 0 else 0
        sl_pct = (risk_distance / entry * 100) if entry > 0 else 0
        tp1 = tp_info.get('tp1', 0) if tp_info else 0

        _log.warning(
            f"\n{'='*60}\n"
            f"  RISK PLAN — REJECTED\n"
            f"{'='*60}\n"
            f"  Symbol:            {symbol}\n"
            f"  Direction:         {direction}\n"
            f"  Setup:             {setup_type}\n"
            f"  Entry:             {entry}\n"
            f"  ATR:               {atr:.6f}\n"
            f"  Structural level:  {structural_level}\n"
            f"  SL:                {sl}\n"
            f"  SL distance:       {risk_distance:.6f}\n"
            f"  SL/ATR:            {sl_atr_ratio:.2f}\n"
            f"  SL distance %:     {sl_pct:.2f}%\n"
            f"  TP:                {tp1}\n"
            f"  RR:                {rr:.2f}\n"
            f"  MAX_SL_ATR:        {MAX_SL_ATR}\n"
            f"  MIN_SL_ATR:        {MIN_SL_ATR}\n"
            f"  MIN_RR:            {MIN_RR}\n"
            f"  SL Reason:         {sl_info.get('reason', '')}\n"
            f"  Reject:            {reject_reason}\n"
            f"{'='*60}"
        )

    def build_trade_plan(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float, symbol: str = "") -> Dict[str, Any]:
        if not ctx:
            return {"valid": False, "reason": "no_context"}

        sl_info = self.calculate_stop_loss(direction, entry, setup_type, ctx, atr)
        if not sl_info or "stop_loss" not in sl_info:
            return {"valid": False, "reason": "sl_calc_failed"}

        sl = sl_info["stop_loss"]
        risk_distance = abs(entry - sl)

        if risk_distance < atr * MIN_SL_ATR:
            tp_info = self.calculate_targets(direction, entry, sl, setup_type, ctx, atr)
            self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, tp_info, risk_distance, 0.0, "sl_too_tight")
            return {"valid": False, "reason": "sl_too_tight", "risk_distance": risk_distance}

        # Do not reject sl_too_wide. Position sizing in executor will adapt amount to keep dollar risk within limits.

        tp_info = self.calculate_targets(direction, entry, sl, setup_type, ctx, atr)
        tp1 = tp_info.get("tp1")
        if not tp1:
            self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, tp_info, risk_distance, 0.0, "tp_calc_failed")
            return {"valid": False, "reason": "tp_calc_failed"}

        if direction == 'LONG':
            if sl >= entry or tp1 <= entry:
                self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, tp_info, risk_distance, 0.0, "invalid_price_geometry")
                return {"valid": False, "reason": "invalid_price_geometry"}
        else:
            if sl <= entry or tp1 >= entry:
                self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, tp_info, risk_distance, 0.0, "invalid_price_geometry")
                return {"valid": False, "reason": "invalid_price_geometry"}
                
        rr = self.calculate_rr(direction, entry, sl, tp1)
        if rr < MIN_RR:
            self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, tp_info, risk_distance, rr, f"rr_too_low_{rr:.2f}")
            return {"valid": False, "reason": f"rr_too_low_{rr:.2f}", "rr": rr}

        return {
            "valid": True,
            "direction": direction,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp1,
            "tp1": tp1,
            "tp2": tp_info.get("tp2"),
            "risk_distance": risk_distance,
            "rr": rr,
            "setup_type": setup_type,
            "sl_reason": sl_info.get("reason"),
            "tp_reason": tp_info.get("reason"),
            "structural_level": sl_info.get("structural_level")
        }

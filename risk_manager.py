import numpy as np
from typing import Dict, Optional, Any
from config import SL_ATR_BUFFER, MIN_SL_ATR, MAX_SL_ATR, MIN_RR, TP_BUFFER_ATR

class StructureRiskEngine:
    def __init__(self):
        pass

    def calculate_stop_loss(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float) -> Dict[str, Any]:
        """
        Calculate structure-based stop loss.
        """
        invalidation_level = None
        reason = ""

        if direction == 'LONG':
            # Base invalidation on setup type
            if setup_type == 'BREAKOUT_RETEST':
                broken_level = ctx.get('broken_level')
                swing_low = ctx.get('swing_low')
                levels = []
                if broken_level is not None:
                    levels.append((broken_level, "below_retest_support"))
                if swing_low is not None:
                    levels.append((swing_low, "below_swing_low"))
                
                if levels:
                    # For LONG, we want the lowest invalidation level to be safe? 
                    # Actually, the user says: "SL должен быть за тем уровнем, который действительно ломает setup. max(broken_level, relevant_swing_low)"
                    # Wait, if we use max(), the SL will be tighter. But we need to make sure we don't put SL inside the structure!
                    # Actually, if broken_level is 100, and swing_low is 98, if we use max(100, 98) = 100, the SL is 100 - buffer.
                    # Wait, "нельзя автоматически выбрать 99.0, если это означает, что обычный шум рынка выбьет позицию... Нужно определить structural invalidation: min(broken_level_based, relevant_swing_low_based)?"
                    # User: "max(broken_level_based_invalidation, relevant_swing_low_based_invalidation) точную сторону сравнения реализовать корректно для LONG."
                    # If we take max(broken_level, swing_low) - wait. 
                    # If entry is 102, broken_level is 100, swing_low is 97. If SL is 99, it might be safe. 
                    # Let's take the lowest support structural point that makes sense.
                    # A breakout retest is invalidated if it falls back below the broken resistance (now support).
                    best_level = levels[0][0]
                    reason = levels[0][1]
                    for lvl, res in levels[1:]:
                        if lvl < best_level:
                            best_level = lvl
                            reason = res
                    invalidation_level = best_level
            
            elif setup_type == 'SUPPORT_BOUNCE':
                sup = ctx.get('nearest_support')
                swing_low = ctx.get('swing_low')
                levels = []
                if sup is not None:
                    levels.append((sup, "below_support_zone"))
                if swing_low is not None:
                    levels.append((swing_low, "below_swing_low"))
                if levels:
                    best_level = min([l[0] for l in levels])
                    reason = "below_support_and_swing_low"
                    invalidation_level = best_level
                    
            elif setup_type == 'LIQUIDITY_SWEEP_LONG':
                sweep_low = ctx.get('sweep_low')
                if sweep_low is not None:
                    invalidation_level = sweep_low
                    reason = "below_sweep_low"
                    
            elif setup_type == 'RESISTANCE_REJECTION':
                # Should not happen for LONG, but fallback
                pass
            
            # Default fallback for LONG
            if invalidation_level is None:
                sup = ctx.get('nearest_support')
                swing_low = ctx.get('swing_low')
                if sup and swing_low:
                    invalidation_level = min(sup, swing_low)
                    reason = "below_nearest_support_or_swing_low"
                elif sup:
                    invalidation_level = sup
                    reason = "below_nearest_support"
                else:
                    invalidation_level = entry - (atr * 2.0)
                    reason = "fallback_atr"

            sl = invalidation_level - (atr * SL_ATR_BUFFER)

            # Check MIN/MAX
            if (entry - sl) < atr * MIN_SL_ATR:
                # Too tight, maybe use swing_low if we used something else?
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
            if setup_type == 'BREAKDOWN_RETEST':
                broken_level = ctx.get('broken_level')
                swing_high = ctx.get('swing_high')
                levels = []
                if broken_level is not None:
                    levels.append((broken_level, "above_retest_resistance"))
                if swing_high is not None:
                    levels.append((swing_high, "above_swing_high"))
                
                if levels:
                    best_level = max([l[0] for l in levels])
                    reason = "above_retest_and_swing_high"
                    invalidation_level = best_level
            
            elif setup_type == 'RESISTANCE_REJECTION':
                res = ctx.get('nearest_resistance')
                swing_high = ctx.get('swing_high')
                rej_high = ctx.get('rejection_high')
                levels = []
                if res is not None:
                    levels.append(res)
                if swing_high is not None:
                    levels.append(swing_high)
                if rej_high is not None:
                    levels.append(rej_high)
                if levels:
                    invalidation_level = max(levels)
                    reason = "above_resistance_and_rejection_high"
                    
            elif setup_type == 'LIQUIDITY_SWEEP_SHORT':
                sweep_high = ctx.get('sweep_high')
                if sweep_high is not None:
                    invalidation_level = sweep_high
                    reason = "above_sweep_high"

            if invalidation_level is None:
                res = ctx.get('nearest_resistance')
                swing_high = ctx.get('swing_high')
                if res and swing_high:
                    invalidation_level = max(res, swing_high)
                    reason = "above_nearest_resistance_or_swing_high"
                elif res:
                    invalidation_level = res
                    reason = "above_nearest_resistance"
                else:
                    invalidation_level = entry + (atr * 2.0)
                    reason = "fallback_atr"

            sl = invalidation_level + (atr * SL_ATR_BUFFER)

            # Check MIN
            if (sl - entry) < atr * MIN_SL_ATR:
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
        """
        Calculate structural take profits.
        """
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
                # Sort targets by price (closest first)
                targets.sort(key=lambda x: x[0])
                tp1_level = targets[0][0]
                tp1 = tp1_level - (atr * TP_BUFFER_ATR)
                reason = targets[0][1]
                if len(targets) > 1 and targets[1][0] > tp1_level:
                    tp2 = targets[1][0] - (atr * TP_BUFFER_ATR)
            else:
                # fallback
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

    def build_trade_plan(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float) -> Dict[str, Any]:
        if not ctx:
            return {"valid": False, "reason": "no_context"}

        sl_info = self.calculate_stop_loss(direction, entry, setup_type, ctx, atr)
        if not sl_info or "stop_loss" not in sl_info:
            return {"valid": False, "reason": "sl_calc_failed"}

        sl = sl_info["stop_loss"]
        risk_distance = abs(entry - sl)

        if risk_distance < atr * MIN_SL_ATR:
            return {"valid": False, "reason": "sl_too_tight", "risk_distance": risk_distance}

        if risk_distance > atr * MAX_SL_ATR:
            return {"valid": False, "reason": "sl_too_wide", "risk_distance": risk_distance}

        tp_info = self.calculate_targets(direction, entry, sl, setup_type, ctx, atr)
        tp1 = tp_info.get("tp1")
        if not tp1:
            return {"valid": False, "reason": "tp_calc_failed"}

        if direction == 'LONG':
            if sl >= entry or tp1 <= entry:
                return {"valid": False, "reason": "invalid_price_geometry"}
        else:
            if sl <= entry or tp1 >= entry:
                return {"valid": False, "reason": "invalid_price_geometry"}
                
        rr = self.calculate_rr(direction, entry, sl, tp1)
        if rr < MIN_RR:
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

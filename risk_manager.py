import numpy as np
from typing import Dict, Optional, Any
from config import SL_ATR_BUFFER, MIN_SL_ATR, MAX_SL_ATR, MIN_RR, TP_BUFFER_ATR, logger

_log = logger.getChild("RiskEngine")

class StructureRiskEngine:
    def __init__(self):
        pass

    def _get_relevant_swing(self, primary_level: float, swing_level: Optional[float], atr: float) -> Optional[float]:
        # Only consider swing low/high relevant if it's within 1.5 ATR of the primary level
        if swing_level is None:
            return None
        if abs(primary_level - swing_level) <= atr * 1.5:
            return swing_level
        return None

    def calculate_stop_loss(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float) -> Dict[str, Any]:
        invalidation_level = None
        reason = ""

        if direction == 'LONG':
            if setup_type == 'BREAKOUT_RETEST':
                broken_level = ctx.get('broken_level')
                swing_low = ctx.get('swing_low')
                levels = []
                if broken_level is not None:
                    levels.append((broken_level, "below_retest_support"))
                    rel_swing = self._get_relevant_swing(broken_level, swing_low, atr)
                    if rel_swing and rel_swing < broken_level:
                        levels.append((rel_swing, "below_relevant_swing_low"))
                elif swing_low is not None:
                    levels.append((swing_low, "below_swing_low"))
                
                if levels:
                    # min() correctly picks the furthest invalidation level for LONG
                    best = min(levels, key=lambda x: x[0])
                    invalidation_level = best[0]
                    reason = best[1]
            
            elif setup_type == 'SUPPORT_BOUNCE' or setup_type == 'TREND_PULLBACK':
                sup = ctx.get('nearest_support')
                swing_low = ctx.get('swing_low')
                levels = []
                if sup is not None:
                    levels.append((sup, "below_support_zone"))
                    rel_swing = self._get_relevant_swing(sup, swing_low, atr)
                    if rel_swing and rel_swing < sup:
                        levels.append((rel_swing, "below_relevant_swing_low"))
                elif swing_low is not None:
                    levels.append((swing_low, "below_swing_low"))
                    
                if levels:
                    best = min(levels, key=lambda x: x[0])
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
                    # Only group if close, otherwise pick sup
                    rel_swing = self._get_relevant_swing(sup, swing_low, atr)
                    if rel_swing:
                        invalidation_level = min(sup, rel_swing)
                        reason = "below_nearest_support_and_relevant_swing_low"
                    else:
                        invalidation_level = sup
                        reason = "below_nearest_support"
                elif sup:
                    invalidation_level = sup
                    reason = "below_nearest_support"
                elif swing_low:
                    invalidation_level = swing_low
                    reason = "below_swing_low"
                else:
                    invalidation_level = entry - (atr * 2.0)
                    reason = "fallback_atr"

            sl = invalidation_level - (atr * SL_ATR_BUFFER)

            if (entry - sl) < atr * MIN_SL_ATR:
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
                    rel_swing = self._get_relevant_swing(broken_level, swing_high, atr)
                    if rel_swing and rel_swing > broken_level:
                        levels.append((rel_swing, "above_relevant_swing_high"))
                elif swing_high is not None:
                    levels.append((swing_high, "above_swing_high"))
                
                if levels:
                    # max() correctly picks the furthest invalidation level for SHORT
                    best = max(levels, key=lambda x: x[0])
                    invalidation_level = best[0]
                    reason = best[1]
            
            elif setup_type in ('RESISTANCE_REJECTION', 'TREND_PULLBACK_DOWN'):
                res = ctx.get('nearest_resistance')
                swing_high = ctx.get('swing_high')
                rej_high = ctx.get('rejection_high')
                
                levels = []
                
                if res is not None:
                    levels.append((res, "above_resistance"))
                    
                    rel_swing = self._get_relevant_swing(res, swing_high, atr)
                    if rel_swing is not None and rel_swing > res:
                        levels.append((rel_swing, "above_relevant_swing_high"))
                        
                if swing_high is not None and res is None:
                    levels.append((swing_high, "above_swing_high"))
                    
                if rej_high is not None:
                    levels.append((rej_high, "above_rejection_high"))
                    
                valid_levels = [
                    (level, reason)
                    for level, reason in levels
                    if level > entry
                ]
                
                if valid_levels:
                    # Для SHORT берём ближайшую валидную структурную инвалидацию
                    # выше entry. Это не позволяет случайно растягивать риск.
                    best = min(valid_levels, key=lambda x: x[0])
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
                    rel_swing = self._get_relevant_swing(res, swing_high, atr)
                    if rel_swing:
                        invalidation_level = max(res, rel_swing)
                        reason = "above_nearest_resistance_and_relevant_swing_high"
                    else:
                        invalidation_level = res
                        reason = "above_nearest_resistance"
                elif res:
                    invalidation_level = res
                    reason = "above_nearest_resistance"
                elif swing_high:
                    invalidation_level = swing_high
                    reason = "above_swing_high"
                else:
                    invalidation_level = entry + (atr * 2.0)
                    reason = "fallback_atr"

            sl = invalidation_level + (atr * SL_ATR_BUFFER)

            if sl <= entry:
                return {
                    "valid": False,
                    "reason": "invalid_short_sl_geometry"
                }

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

    def calculate_directional_rr(
        self,
        direction: str,
        entry: float,
        stop_loss: float,
        target: float
    ):
        if direction == "LONG":
            risk = entry - stop_loss
            reward = target - entry
        elif direction == "SHORT":
            risk = stop_loss - entry
            reward = entry - target
        else:
            return 0.0, 0.0, 0.0

        if risk <= 0 or reward <= 0:
            return risk, reward, 0.0

        return risk, reward, reward / risk

    def build_trade_plan(self, direction: str, entry: float, setup_type: str, ctx: Dict[str, Any], atr: float, max_distance: Optional[float] = None) -> Dict[str, Any]:
        if not ctx:
            return {"valid": False, "reason": "no_context"}

        sl_info = self.calculate_stop_loss(direction, entry, setup_type, ctx, atr)
        if not sl_info or "stop_loss" not in sl_info:
            return {"valid": False, "reason": "sl_calc_failed"}

        sl = sl_info["stop_loss"]
        
        if direction == "LONG":
            risk_distance = entry - sl
        else:
            risk_distance = sl - entry

        if risk_distance <= 0:
            return {
                "valid": False,
                "reason": "invalid_risk_geometry"
            }

        if risk_distance < atr * MIN_SL_ATR:
            return {"valid": False, "reason": "sl_too_tight", "risk_distance": risk_distance}

        if max_distance is not None:
            if risk_distance > max_distance:
                return {"valid": False, "reason": "sl_too_wide_for_min_notional", "risk_distance": risk_distance}
        else:
            # When max_distance is not provided, we don't reject blindly on MAX_SL_ATR because we want position sizing to handle it.
            # However, if it's absurdly wide (e.g. > 10 ATR), we reject it.
            if risk_distance > atr * (MAX_SL_ATR * 3):
                return {"valid": False, "reason": "sl_too_wide", "risk_distance": risk_distance}

        tp_info = self.calculate_targets(direction, entry, sl, setup_type, ctx, atr)
        tp1 = tp_info.get("tp1")
        if not tp1:
            return {"valid": False, "reason": "tp_calc_failed"}

        risk_distance, reward_distance, rr = self.calculate_directional_rr(
            direction=direction,
            entry=entry,
            stop_loss=sl,
            target=tp1
        )
        
        if risk_distance <= 0 or reward_distance <= 0:
            return {
                "valid": False,
                "reason": "invalid_reward_geometry",
                "risk_distance": risk_distance,
                "reward_distance": reward_distance
            }

        _log.warning(
            "[RISK DEBUG] "
            f"setup={setup_type} "
            f"direction={direction} "
            f"entry={entry:.8f} "
            f"sl={sl:.8f} "
            f"tp={tp1:.8f} "
            f"risk={risk_distance:.8f} "
            f"reward={reward_distance:.8f} "
            f"rr={rr:.4f} "
            f"atr={atr:.8f} "
            f"sl_reason={sl_info.get('reason')} "
            f"tp_reason={tp_info.get('reason')} "
            f"support={ctx.get('nearest_support')} "
            f"resistance={ctx.get('nearest_resistance')} "
            f"swing_high={ctx.get('swing_high')} "
            f"swing_low={ctx.get('swing_low')} "
            f"rejection_high={ctx.get('rejection_high')}"
        )
        
        if rr < MIN_RR:
            return {
                "valid": False,
                "reason": f"rr_too_low_{rr:.2f}",
                "rr": rr,
                "risk_distance": risk_distance,
                "reward_distance": reward_distance
            }

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


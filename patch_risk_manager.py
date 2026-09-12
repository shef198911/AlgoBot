import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Widen SL instead of rejecting 'sl_too_tight'
target_sl = """        if risk_distance < atr * MIN_SL_ATR:
            return {"valid": False, "reason": "sl_too_tight", "risk_distance": risk_distance}"""

replacement_sl = """        if risk_distance < atr * MIN_SL_ATR:
            # Widen SL to minimum allowed distance instead of rejecting
            if direction == "LONG":
                sl = entry - (atr * MIN_SL_ATR)
            else:
                sl = entry + (atr * MIN_SL_ATR)
            risk_distance = atr * MIN_SL_ATR"""

content = content.replace(target_sl, replacement_sl)

# 2. Set TP to MIN_RR distance instead of rejecting 'rr_too_low'
target_rr = """        if selected_target is None:
            return {
                "valid": False,
                "reason": f"rr_too_low_best_{best_candidate_rr:.2f}",
                "rr": best_candidate_rr,
                "risk_distance": risk_distance,
                "dynamic_tp_pct": dynamic_tp_pct,
                "candidate_targets": [
                    {
                        "price": price,
                        "reason": reason
                    }
                    for price, reason in target_candidates
                ]
            }"""

replacement_rr = """        if selected_target is None:
            # Instead of rejecting, calculate a TP that strictly satisfies MIN_RR
            if direction == "LONG":
                selected_target = entry + (risk_distance * MIN_RR)
            else:
                selected_target = entry - (risk_distance * MIN_RR)
            selected_reason = "forced_min_rr_target"
            
            # Recalculate RR just to populate variables correctly
            _, selected_reward, selected_rr = self.calculate_directional_rr(
                direction=direction,
                entry=entry,
                stop_loss=sl,
                target=selected_target
            )"""

content = content.replace(target_rr, replacement_rr)

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("risk_manager.py patched!")

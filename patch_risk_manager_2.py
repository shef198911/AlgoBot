import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the "forced_min_rr_target" logic to include an absolute cap check.
target_fallback = """        if selected_target is None:
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

replacement_fallback = """        is_technical_fallback = False
        if selected_target is None:
            # Calculate a TP that strictly satisfies MIN_RR
            if direction == "LONG":
                selected_target = entry + (risk_distance * MIN_RR)
                max_tp_limit = entry + (atr * 5.0) # Upper bound: 5 ATR
                if selected_target > max_tp_limit:
                    return {
                        "valid": False,
                        "reason": "technical_tp_exceeds_max_limit",
                        "rr": best_candidate_rr,
                        "risk_distance": risk_distance
                    }
            else:
                selected_target = entry - (risk_distance * MIN_RR)
                max_tp_limit = entry - (atr * 5.0)
                if selected_target < max_tp_limit:
                    return {
                        "valid": False,
                        "reason": "technical_tp_exceeds_max_limit",
                        "rr": best_candidate_rr,
                        "risk_distance": risk_distance
                    }
            selected_reason = "technical_min_rr_target"
            is_technical_fallback = True
            
            _, selected_reward, selected_rr = self.calculate_directional_rr(
                direction=direction,
                entry=entry,
                stop_loss=sl,
                target=selected_target
            )"""

content = content.replace(target_fallback, replacement_fallback)

# 2. Update logging at the end of build_trade_plan to meet the user's specific output format.
target_log = """        _log.warning(
            "[RISK PLAN] "
            f"setup={setup_type} "
            f"direction={direction} "
            f"entry={entry:.8f} "
            f"sl={sl:.8f} "
            f"tp={tp1:.8f} "
            f"risk_pct={(risk_distance / entry) * 100:.3f}% "
            f"reward_pct={(reward_distance / entry) * 100:.3f}% "
            f"rr={rr:.3f} "
            f"dynamic_tp_pct={dynamic_tp_pct} "
            f"tp_reason={tp_info.get('reason')} "
            f"structural_tp1={structural_tp1} "
            f"structural_tp2={structural_tp2} "
            f"sl_reason={sl_info.get('reason')}"
        )"""

replacement_log = """        _log.warning(
            f"[RISK PLAN] setup={setup_type} direction={direction}\n"
            f"  entry={entry:.8f} sl={sl:.8f} tp={tp1:.8f}\n"
            f"  structural TP candidates: {[f'{c[0]:.5f} ({c[1]})' for c in target_candidates if 'ai' not in c[1]]}\n"
            f"  AI TP: {ai_tp if 'ai_tp' in locals() and ai_tp is not None else 'None'}\n"
            f"  best_candidate_rr={best_candidate_rr:.3f}\n"
            f"  selected_tp={tp1:.8f} reason={selected_reason}\n"
            f"  final_rr={rr:.3f} fallback_used={is_technical_fallback}\n"
            f"  sl_reason={sl_info.get('reason')}"
        )"""

content = content.replace(target_log, replacement_log)

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("risk_manager.py patched for upper bound and detailed logging.")

import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the formatting of the logs
target_log = """        _log.warning(
            f"[RISK PLAN] setup={setup_type} direction={direction}\\n"
            f"  entry={entry:.8f} sl={sl:.8f} tp={tp1:.8f}\\n"
            f"  structural TP candidates: {[f'{c[0]:.5f} ({c[1]})' for c in target_candidates if 'ai' not in c[1]]}\\n"
            f"  AI TP: {ai_tp if 'ai_tp' in locals() and ai_tp is not None else 'None'}\\n"
            f"  best_candidate_rr={best_candidate_rr:.3f}\\n"
            f"  selected_tp={tp1:.8f} reason={selected_reason}\\n"
            f"  final_rr={rr:.3f} fallback_used={is_technical_fallback}\\n"
            f"  sl_reason={sl_info.get('reason')}"
        )"""

replacement_log = """        # Generate detailed candidate string with RR info
        cand_details = []
        ai_details = "None"
        for candidate_target, candidate_reason in target_candidates:
            _, _, c_rr = self.calculate_directional_rr(direction, entry, sl, candidate_target)
            if 'ai' in candidate_reason:
                ai_details = f"{candidate_target:.5f} (RR={c_rr:.3f})"
            else:
                cand_details.append(f"{candidate_target:.5f} (RR={c_rr:.3f})")

        _log.warning(
            f"[RISK PLAN] setup={setup_type} direction={direction}\\n"
            f"  entry={entry:.8f} sl={sl:.8f} tp={tp1:.8f}\\n"
            f"  structural TP candidates: {', '.join(cand_details)}\\n"
            f"  AI TP: {ai_details}\\n"
            f"  best_candidate_rr={best_candidate_rr:.3f}\\n"
            f"  selected_tp={tp1:.8f} reason={selected_reason}\\n"
            f"  final_rr={rr:.3f} fallback_used={is_technical_fallback}\\n"
            f"  sl_reason={sl_info.get('reason')}"
        )"""

content = content.replace(target_log, replacement_log)

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("risk_manager.py patched for logging with RR details.")

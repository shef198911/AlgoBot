import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        selected_target = None
        selected_reason = None
        selected_rr = 0.0
        selected_reward = 0.0

        for candidate_target, candidate_reason in target_candidates:

            candidate_risk, candidate_reward, candidate_rr = self.calculate_directional_rr(
                direction=direction,
                entry=entry,
                stop_loss=sl,
                target=candidate_target
            )

            if candidate_risk <= 0 or candidate_reward <= 0:
                continue

            if candidate_rr >= MIN_RR:
                selected_target = candidate_target
                selected_reason = candidate_reason
                selected_rr = candidate_rr
                selected_reward = candidate_reward
                break

        if selected_target is None:
            # Ни одна потенциальная структурная цель не обеспечит нужный RR.
            # Для отладки берем первую, и возвращаем отрицательный ответ.
            first_target = target_candidates[0][0]

            _, first_reward, first_rr = self.calculate_directional_rr(
                direction=direction,
                entry=entry,
                stop_loss=sl,
                target=first_target
            )

            return {
                "valid": False,
                "reason": f"rr_too_low_{first_rr:.2f}",
                "rr": first_rr,
                "risk_distance": risk_distance,
                "reward_distance": first_reward,
                "dynamic_tp_pct": dynamic_tp_pct,
                "candidate_targets": [
                    {
                        "price": price,
                        "reason": reason
                    }
                    for price, reason in target_candidates
                ]
            }"""

replacement = """        selected_target = None
        selected_reason = None
        selected_rr = 0.0
        selected_reward = 0.0

        best_candidate_rr = 0.0
        best_candidate_price = None
        best_candidate_reason = None

        for candidate_target, candidate_reason in target_candidates:

            candidate_risk, candidate_reward, candidate_rr = self.calculate_directional_rr(
                direction=direction,
                entry=entry,
                stop_loss=sl,
                target=candidate_target
            )

            if candidate_risk <= 0 or candidate_reward <= 0:
                continue

            if candidate_rr > best_candidate_rr:
                best_candidate_rr = candidate_rr
                best_candidate_price = candidate_target
                best_candidate_reason = candidate_reason

            if candidate_rr >= MIN_RR:
                selected_target = candidate_target
                selected_reason = candidate_reason
                selected_rr = candidate_rr
                selected_reward = candidate_reward
                break

        if selected_target is None:
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

content = content.replace(target, replacement)

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

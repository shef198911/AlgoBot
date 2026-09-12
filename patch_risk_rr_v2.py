import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_loop = False
replaced = False

i = 0
while i < len(lines):
    line = lines[i]
    
    if "selected_target = None" in line and not replaced:
        new_lines.append(line)
        new_lines.append("        selected_reason = None\n")
        new_lines.append("        selected_rr = 0.0\n")
        new_lines.append("        selected_reward = 0.0\n")
        new_lines.append("\n")
        new_lines.append("        best_candidate_rr = 0.0\n")
        new_lines.append("        best_candidate_price = None\n")
        new_lines.append("        best_candidate_reason = None\n")
        
        # Skip the original initializations
        i += 4
        
        # Now we process the for loop
        while i < len(lines) and "if selected_target is None:" not in lines[i]:
            if "if candidate_rr >= MIN_RR:" in lines[i]:
                new_lines.append("            if candidate_rr > best_candidate_rr:\n")
                new_lines.append("                best_candidate_rr = candidate_rr\n")
                new_lines.append("                best_candidate_price = candidate_target\n")
                new_lines.append("                best_candidate_reason = candidate_reason\n\n")
            new_lines.append(lines[i])
            i += 1
            
        # We hit "if selected_target is None:"
        new_lines.append(lines[i]) # if selected_target is None:
        
        # We want to replace everything inside this block
        return_block = """            return {
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
            }\n"""
        
        new_lines.append(return_block)
        
        # skip lines until the end of the return dict
        while i < len(lines) and "tp1 = selected_target" not in lines[i]:
            i += 1
        
        # Now i is at "tp1 = selected_target"
        new_lines.append("\n")
        new_lines.append(lines[i])
        replaced = True
        
    else:
        new_lines.append(line)
    
    i += 1

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Replaced:", replaced)

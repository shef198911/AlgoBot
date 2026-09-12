import re

with open('G:/AlgoBot/risk_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        return {
            "valid": True,
            "direction": direction,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp1,"""

replacement = """        return {
            "valid": True,
            "direction": direction,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp1,
            "reason": selected_reason,"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Added reason to valid response in risk_manager.py")

import re

with open('G:/AlgoBot/capital_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    # Final hard checks
    if risk_usdt_actual > requested_risk + 1e-8:
        return {
            "valid": False,
            "reason": "actual_risk_exceeds_requested_risk",
            "risk_usdt_actual": risk_usdt_actual,
            "risk_usdt_requested": requested_risk,
        }"""

replacement = """    # Final hard checks
    if risk_usdt_actual > requested_risk + 1e-8:
        print(f"DEBUG: amount_coin={amount_coin}, sl_distance={sl_distance}, risk_usdt_actual={risk_usdt_actual}, requested_risk={requested_risk}")
        return {
            "valid": False,
            "reason": "actual_risk_exceeds_requested_risk",
            "risk_usdt_actual": risk_usdt_actual,
            "risk_usdt_requested": requested_risk,
        }"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/capital_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added debug to capital_manager")

import re

with open('G:/AlgoBot/capital_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """def get_portfolio_risk_usdt(positions: dict) -> float:
    \"\"\"Sum of risk_usdt across all open positions.\"\"\"
    return sum(
        pos.get('risk_usdt', 0.0)
        for pos in positions.values()
        if pos.get('status') in ('OPEN', 'UNKNOWN', None)
    )"""

replacement = """def get_portfolio_risk_usdt(positions: dict) -> float:
    \"\"\"Sum of risk_usdt across all open positions.\"\"\"
    return sum(
        float(pos.get('risk_usdt_actual', pos.get('risk_usdt_requested', pos.get('risk_usdt', 0.0))))
        for pos in positions.values()
        if pos.get('status') in ('OPEN', 'UNKNOWN', None)
    )"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/capital_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed get_portfolio_risk_usdt key")

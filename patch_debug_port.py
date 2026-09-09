import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            # 10. FINAL PORTFOLIO RISK
            current_portfolio_risk = get_portfolio_risk_usdt(self.positions)
            from config import MAX_TOTAL_PORTFOLIO_RISK_PCT
            max_portfolio_risk = effective_cap * MAX_TOTAL_PORTFOLIO_RISK_PCT / 100.0
            projected_portfolio_risk = current_portfolio_risk + risk_usdt_actual"""

replacement = """            # 10. FINAL PORTFOLIO RISK
            current_portfolio_risk = get_portfolio_risk_usdt(self.positions)
            print(f"DEBUG_PORTFOLIO: positions={self.positions}, current={current_portfolio_risk}, risk_usdt={risk_usdt_actual}")
            from config import MAX_TOTAL_PORTFOLIO_RISK_PCT
            max_portfolio_risk = effective_cap * MAX_TOTAL_PORTFOLIO_RISK_PCT / 100.0
            projected_portfolio_risk = current_portfolio_risk + risk_usdt_actual"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added DEBUG_PORTFOLIO to execute_trade")

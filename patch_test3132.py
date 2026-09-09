import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace 'filled': 0.5 with 'filled': 0.01
content = re.sub(r"'filled': 0\.5", r"'filled': 0.01", content)

# Replace 'positionAmt': '0.5' with 'positionAmt': '0.01'
content = re.sub(r"'positionAmt': '0\.5'", r"'positionAmt': '0.01'", content)

# Replace amount: 0.5 with amount: 0.01 in fetch_open_orders
content = re.sub(r"'amount': 0\.5", r"'amount': 0.01", content)

# Replace execute_trade risk_pct=0.5 with risk_pct=1.0 just to be consistent
# content = re.sub(r"executor\.execute_trade\('BTC/USDT', 'buy', 0\.5,", r"executor.execute_trade('BTC/USDT', 'buy', 1.0,", content)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 31 and 32 fill amounts")

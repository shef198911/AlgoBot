import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """mock_ex.fetch_my_trades = MagicMock(return_value=[{'side': 'sell', 'price': 100.0, 'info': {'realizedPnl': '0'}}])"""

import time
ts = int(time.time() * 1000)

replacement = f"""mock_ex.fetch_my_trades = MagicMock(return_value=[{{'side': 'sell', 'price': 100.0, 'timestamp': {ts}, 'info': {{'realizedPnl': '0'}}}}])"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 44 to include timestamp")

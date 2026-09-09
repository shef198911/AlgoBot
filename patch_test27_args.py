import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

target27 = "success = executor.execute_trade('BTC/USDT', 'buy', 1.0, 50000.0, 100.0, 0.05, 'BREAKOUT_RETEST')"
replacement27 = "success = executor.execute_trade('BTC/USDT', 'buy', 1.0, 50000.0, 100.0, setup_type='BREAKOUT_RETEST', engine_context={'mock': True})"

content = content.replace(target27, replacement27)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 27 arguments")

import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("executor.calculate_sl_tp = MagicMock(return_value=(90.0, 110.0))", "executor.calculate_sl_tp = MagicMock(return_value=(90.0, 120.0))")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated all tests tp to fix RR")

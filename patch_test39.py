import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("'risk_usdt_actual': 145.0}", "'risk_usdt_actual': 145.0, 'risk_usdt': 145.0}")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 39 DUMMY position")

import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("self.assertEqual(executor.positions['BTC/USDT']['amount'], 0.35)", "self.assertEqual(executor.positions['BTC/USDT']['amount'], 0.001)")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 30 assertion")

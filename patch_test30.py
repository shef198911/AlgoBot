import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences of 0.35 with 0.001 in test_30
content = re.sub(r"'positionAmt': '0\.35'", r"'positionAmt': '0.001'", content)
content = re.sub(r"'filled': 0\.35", r"'filled': 0.001", content)
content = re.sub(r"'amount': 0\.35", r"'amount': 0.001", content)
content = re.sub(r"amount\], 0\.35\)", r"amount], 0.001)", content)
content = re.sub(r"self\.assertEqual\(sl_call\[0\]\[3\], 0\.35\)", r"self.assertEqual(sl_call[0][3], 0.001)", content)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 30 partial fill amount")

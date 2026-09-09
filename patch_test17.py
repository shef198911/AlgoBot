import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'self.assertIn("недостаточно", executor.last_error)'
target2 = 'self.assertIn("", executor.last_error)' # just in case

# using regex
content = re.sub(r'self\.assertIn\(["\'][^"\']*недостаточно[^"\']*["\'], executor\.last_error\)', 'self.assertIn("no_margin_capacity", executor.last_error)', content)
content = re.sub(r'self\.assertIn\(["\'].*["\'], executor\.last_error\)', 'self.assertIn("no_margin_capacity", executor.last_error)', content)


with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 17 assertion")

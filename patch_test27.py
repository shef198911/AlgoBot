import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

target27 = "mock_ex.price_to_precision.side_effect = lambda sym, p: f\"{p:.2f}\""
replacement27 = """mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.amount_to_precision.side_effect = lambda sym, a: f"{a:.4f}" """

content = content.replace(target27, replacement27)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 27 amount precision mock")

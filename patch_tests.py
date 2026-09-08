with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace("'stopPrice': 49000.0, 'amount': 0.35", "'stopPrice': 48500.0, 'amount': 0.35")
code = code.replace("'stopPrice': 49000.0, 'amount': 0.5", "'stopPrice': 48500.0, 'amount': 0.5")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(code)

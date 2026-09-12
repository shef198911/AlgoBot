import re

with open('G:/AlgoBot/desktop_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = "contracts = float(pos.get('contracts', 0))"
replacement = """amt_str = pos.get('info', {}).get('positionAmt', pos.get('contracts', 0))
                contracts = abs(float(amt_str)) if amt_str else 0.0"""

if target in content:
    content = content.replace(target, replacement)
    with open('G:/AlgoBot/desktop_app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed desktop_app.py")
else:
    print("Target not found in desktop_app.py")

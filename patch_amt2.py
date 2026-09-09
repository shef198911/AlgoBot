import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            if not actual_position_amount and order and order.get('filled'):
                actual_position_amount = float(order.get('filled'))
            
            if not actual_position_amount:
                actual_position_amount = amount_coin"""

replacement = """            if not actual_position_amount and order and order.get('filled'):
                actual_position_amount = float(order.get('filled'))"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed amount_coin fallback")

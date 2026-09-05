import re

with open('executor.py', 'r', encoding='utf-8') as f:
    exec_source = f.read()

exec_source = exec_source.replace("position_opened = False\n        actual_position_amount = None\n        try:", "position_opened = False\n        actual_position_amount = None\n        sl_order_id = None\n        try:")
exec_source = exec_source.replace("if position_opened:", "if position_opened and not sl_order_id:")

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(exec_source)

with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We will just replace exactly the string:
# 'f.write(f"{time.strftime(\'%Y-%m-%d %H:%M:%S\')} | {symbol} | {side_str.upper()} | Вход: {current_price}\\n")'

target = r'f\.write\(f"\{time\.strftime\(\'%Y-%m-%d %H:%M:%S\'\)\} \| \{symbol\} \| \{side_str\.upper\(\)\} \| [^:]+: \{current_price\}\\n"\)'
replacement = """time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{time_str} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}\\n")"""

content = re.sub(target, replacement, content)

with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py safely patched")

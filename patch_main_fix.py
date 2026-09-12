import re

with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will just find the block:
#            with open("trade_history.txt", "a", encoding="utf-8") as f:
#                time_str = ...
# ...
#          else:

import re

# Find everything from "tg.send_message(" until "else:"
# and replace the writing block

def fix_main(text):
    lines = text.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'tg.send_message(f"🚀 <b>' in line or 'tg.send_message(f"🚀' in line or 'tg.send_message' in line and 'открыта' in line.lower():
            new_lines.append(line)
            # The next lines are the with open block that is broken.
            # Skip until we see `        else:`
            new_lines.append('            time_str = time.strftime("%Y-%m-%d %H:%M:%S")')
            new_lines.append('            with open("trade_history.txt", "a", encoding="utf-8") as f:')
            new_lines.append('                f.write(f"{time_str} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}\\n")')
            i += 1
            while i < len(lines) and '        else:' not in lines[i]:
                i += 1
            continue
        new_lines.append(line)
        i += 1
    return '\n'.join(new_lines)

new_content = fix_main(content)
with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("main.py repaired!")

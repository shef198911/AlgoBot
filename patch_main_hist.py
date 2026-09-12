import re

with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = "f.write(f\"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | {side_str.upper()} | Вход: {current_price}\\n\")"
replacement = "f.write(f\"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price} | SL: {sl} | TP: {tp}\\n\")"

# If exact Russian word is scrambled, let's use a regex
content = re.sub(r'f\.write\(f"\{time\.strftime\(\'%Y-%m-%d %H:%M:%S\'\)\} \| \{symbol\} \| \{side_str\.upper\(\)\} \| .*?\{current_price\}\\n"\)',
                 r'f.write(f"{time.strftime(\'%Y-%m-%d %H:%M:%S\')} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price} | SL: {sl} | TP: {tp}\\n")',
                 content)

with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

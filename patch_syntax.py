with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Fix syntax error in main.py
target_regex = r'f\.write\(f"\{time\.strftime\(\\\'\%Y-\%m-\%d \%H:\%M:\%S\\\'\)\}.*?\\n"\)'
replacement = """time_str = time.strftime('%Y-%m-%d %H:%M:%S')
            with open("trade_history.txt", "a", encoding="utf-8") as f:
                f.write(f"{time_str} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}\\n")"""
content = re.sub(r'f\.write\(f"\{time\.strftime.*?\)', replacement, content)

# But wait, it might be easier to just match the `with open` block:
content = re.sub(
    r'with open\("trade_history\.txt", "a", encoding="utf-8"\) as f:\n\s+f\.write\(f"\{time\.strftime.*?\\n"\)',
    replacement,
    content
)

with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py fixed!")

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Remove `import time` from the injected block in executor.py
content = content.replace('                            import time\n', '')
# also `time.strftime('%Y-%m-%d %H:%M:%S')` -> `time_str` is safer, but time is imported at module level in executor.py so it's fine.

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("executor.py fixed!")

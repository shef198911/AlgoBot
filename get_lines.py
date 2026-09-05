
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
with open('executor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'tg_notifier.send_message' in line and 'new_sl_price' in line:
        for j in range(i-15, i+15):
            print(f'{j}: {lines[j].rstrip()}')


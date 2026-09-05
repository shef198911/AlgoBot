import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('                        def get_global_trend'):
        new_lines.append('            def get_global_trend(row):\n')
    elif line.startswith('                        def get_confirmed_signal'):
        new_lines.append('            def get_confirmed_signal(row):\n')
    else:
        new_lines.append(line)

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

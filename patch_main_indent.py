import sys

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('                        trend_str'):
        new_lines.append(line.replace('                        ', '                ', 1))
    elif line.startswith('                        analyzed_data'):
        new_lines.append(line.replace('                        ', '                ', 1))
    else:
        new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

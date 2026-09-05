import sys

with open('entry_gate.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace('\ufeff', '')

with open('entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(source)

print("BOM removed.")

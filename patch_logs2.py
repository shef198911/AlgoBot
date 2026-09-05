import sys

with open('entry_gate.py', 'r', encoding='utf-8') as f:
    source = f.read()

if "LOG_ENTRY_GATE = True" not in source:
    source = "LOG_ENTRY_GATE = True\n" + source

source = source.replace('if symbol != "UNKNOWN":', 'if LOG_ENTRY_GATE:')

with open('entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(source)

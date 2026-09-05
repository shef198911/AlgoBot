import sys

with open('train_model.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_import = "from strategy_ta import TAStrategy"
new_import = "from strategy_ta import TAStrategy\nimport entry_gate\n\nentry_gate.LOG_ENTRY_GATE = False"

source = source.replace(old_import, new_import)

with open('train_model.py', 'w', encoding='utf-8') as f:
    f.write(source)

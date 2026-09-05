
with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace('row.get(\"GLOBAL_TREND\", \"RANGE\")', 'row.get(\"HTF_TREND\", row.get(\"GLOBAL_TREND\", \"RANGE\"))')

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)


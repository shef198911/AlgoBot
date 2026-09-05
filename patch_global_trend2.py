import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace('global_trend = get_global_trend(row)', "global_trend = row.get('GLOBAL_TREND', 'RANGE')")

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

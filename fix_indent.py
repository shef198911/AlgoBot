import re

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    for line in lines:
        if 'effective_trend = htf_trend' in line:
            f.write('                effective_trend = htf_trend if htf_trend is not None else row.get(\"GLOBAL_TREND\", \"RANGE\")\n')
        elif 'is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str)' in line:
            f.write('                is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str)\n')
        else:
            f.write(line)

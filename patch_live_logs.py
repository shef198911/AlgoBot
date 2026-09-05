import sys

# Patch entry_gate.py
with open('entry_gate.py', 'r', encoding='utf-8') as f:
    eg_source = f.read()

if 'def validate(row, global_trend, symbol="UNKNOWN", do_log=True):' not in eg_source:
    eg_source = eg_source.replace(
        'def validate(row, global_trend, symbol="UNKNOWN"):',
        'def validate(row, global_trend, symbol="UNKNOWN", do_log=True):'
    )
    
    eg_source = eg_source.replace(
        'if LOG_ENTRY_GATE:',
        'if LOG_ENTRY_GATE and do_log:'
    )
    
    with open('entry_gate.py', 'w', encoding='utf-8') as f:
        f.write(eg_source)

# Patch strategy_ta.py
with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    sta_source = f.read()

old_loop = """            symbol_str = getattr(self, "current_symbol", "UNKNOWN")
            for _, row in data.iterrows():
                effective_trend = htf_trend if htf_trend is not None else row.get("HTF_TREND", row.get("GLOBAL_TREND", "RANGE"))
                is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str)"""

new_loop = """            symbol_str = getattr(self, "current_symbol", "UNKNOWN")
            total_rows = len(data)
            for i, (_, row) in enumerate(data.iterrows()):
                effective_trend = htf_trend if htf_trend is not None else row.get("HTF_TREND", row.get("GLOBAL_TREND", "RANGE"))
                is_last = (i == total_rows - 1)
                is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str, do_log=is_last)"""

if "do_log=is_last" not in sta_source:
    sta_source = sta_source.replace(old_loop, new_loop)
    with open('strategy_ta.py', 'w', encoding='utf-8') as f:
        f.write(sta_source)

print("Patch applied.")

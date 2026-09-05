import sys

with open('test_entry_gate.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace("eng_setup == 'LIQUIDITY_SWEEP'", "eng_setup == 'LIQUIDITY_SWEEP_LONG'")
source = source.replace("eng_setup='LIQUIDITY_SWEEP'", "engine_setup='LIQUIDITY_SWEEP_LONG'")
source = source.replace("engine_setup='LIQUIDITY_SWEEP_SHORT'", "engine_setup='LIQUIDITY_SWEEP_SHORT'") # just in case

source = source.replace("eng_setup == 'TREND_PULLBACK'", "eng_setup == 'TREND_PULLBACK'")
source = source.replace("eng_setup == 'TREND_PULLBACK_DOWN'", "eng_setup == 'TREND_PULLBACK_DOWN'")

with open('test_entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(source)

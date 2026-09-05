import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Replace setup names
source = source.replace('elif eng_setup == "LIQUIDITY_SWEEP":', 'elif eng_setup == "LIQUIDITY_SWEEP_LONG" or eng_setup == "LIQUIDITY_SWEEP_SHORT":')
source = source.replace('elif eng_setup == "TREND_PULLBACK":', 'elif eng_setup == "TREND_PULLBACK" or eng_setup == "TREND_PULLBACK_DOWN":')
source = source.replace('elif eng_setup == "RANGE_BOUNCE":', 'elif eng_setup == "RANGE_BOUNCE" or eng_setup == "RANGE_REJECTION" or eng_setup == "SUPPORT_BOUNCE" or eng_setup == "RESISTANCE_REJECTION":')

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

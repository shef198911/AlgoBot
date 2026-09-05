import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

stats_code = """
# Global entry statistics
entry_stats = {
    'TA_CANDIDATES': 0,
    'ENTRY_GATE_PASS': 0,
    'REJECT_NO_BROKEN_LEVEL': 0,
    'REJECT_NO_CONFIRMATION': 0,
    'REJECT_BAD_STRUCTURE': 0,
    'REJECT_BAD_GLOBAL_TREND': 0,
    'REJECT_CANDLE_CLOSE': 0,
    'REJECT_NO_REAL_SWEEP': 0,
    'REJECT_NOT_IN_RANGE': 0,
    'REJECT_UNKNOWN_SETUP': 0,
    'REJECT_LOW_SCORE': 0,
    'REJECT_SR_TOO_CLOSE': 0,
    'REJECT_RSI_EXTREME': 0
}
"""

# Insert right before class TAStrategy
for i, line in enumerate(lines):
    if line.startswith('class TAStrategy:'):
        lines.insert(i, stats_code)
        break

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

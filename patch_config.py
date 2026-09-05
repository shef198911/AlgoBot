import sys

with open('config.py', 'r', encoding='utf-8') as f:
    source = f.read()

config_str = """
# Risk Engine Settings (Structure-based)
STRUCTURE_RISK_ENABLED = True
SL_ATR_BUFFER = 0.25
MIN_SL_ATR = 0.5
MAX_SL_ATR = 3.0
MIN_RR = 1.5
TP_BUFFER_ATR = 0.10
"""
if "STRUCTURE_RISK_ENABLED" not in source:
    with open('config.py', 'a', encoding='utf-8') as f:
        f.write("\n" + config_str)

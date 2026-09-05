import sys
import re

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Replace distance checks
old_res = "elif row.get('DIST_RES_PCT', 1.0) < min_sr:"
new_res = """
                        sr_strength = row.get('SR_STRENGTH', 50.0)
                        req_dist_res = min_sr * max(1.0, (sr_strength / 50.0))
                        if row.get('DIST_RES_PCT', 1.0) < req_dist_res:"""

source = source.replace(old_res, new_res.lstrip('\n'))

old_sup = "elif row.get('DIST_SUP_PCT', 1.0) < min_sr:"
new_sup = """
                        sr_strength = row.get('SR_STRENGTH', 50.0)
                        req_dist_sup = min_sr * max(1.0, (sr_strength / 50.0))
                        if row.get('DIST_SUP_PCT', 1.0) < req_dist_sup:"""

source = source.replace(old_sup, new_sup.lstrip('\n'))

# Add stats tracking
# We will create global dict in strategy_ta.py
stats_code = """
import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator

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
source = source.replace('import pandas as pd\nfrom ta.trend import EMAIndicator, ADXIndicator', stats_code)

# Now modify get_confirmed_signal to update entry_stats
# Inside get_confirmed_signal(row)
# I'll just run a regex to inject the stat update before returns
# Wait, it's easier to just replace the whole get_confirmed_signal again.

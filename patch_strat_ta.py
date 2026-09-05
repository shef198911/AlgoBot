import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Replace generate_features_and_signals(self, df):
source = source.replace('def generate_features_and_signals(self, df):', 'def generate_features_and_signals(self, df, htf_trend="RANGE"):')

# Remove entry_stats definition from strategy_ta.py, we will import it from entry_gate
import_entry_gate = "from entry_gate import EntryGate, entry_stats\n"
source = source.replace('class TAStrategy:', import_entry_gate + 'class TAStrategy:')

# We need to remove the inline entry_stats from strategy_ta.py
# It's at the top, let's just strip it out.
import re
source = re.sub(r'# Global entry statistics\s+entry_stats = \{.*?\n\}\n', '', source, flags=re.DOTALL)

# Replace get_confirmed_signal
old_get_confirmed = re.search(r'            def get_confirmed_signal\(row\):.*?results = \[get_confirmed_signal\(row\) for _, row in data.iterrows()\]', source, flags=re.DOTALL).group(0)

new_get_confirmed = '''            results = []
            symbol_str = getattr(self, "current_symbol", "UNKNOWN")
            for _, row in data.iterrows():
                is_valid, reject_reason = EntryGate.validate(row, htf_trend, symbol_str)
                if is_valid:
                    results.append((row.get('engine_signal', 0), row.get('engine_setup', 'None')))
                else:
                    results.append((0, "None"))'''

source = source.replace(old_get_confirmed, new_get_confirmed)

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

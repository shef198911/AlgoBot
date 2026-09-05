import sys

def patch_strategy():
    with open('strategy_ta.py', 'r', encoding='utf-8') as f:
        source = f.read()
        
    source = source.replace('def generate_features_and_signals(self, df, htf_trend="RANGE"):', 'def generate_features_and_signals(self, df, htf_trend=None):')
    
    old_loop = "is_valid, reject_reason = EntryGate.validate(row, htf_trend, symbol_str)"
    new_loop = """                  effective_trend = htf_trend if htf_trend is not None else row.get('GLOBAL_TREND', 'RANGE')
                  is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str)"""
                  
    source = source.replace(old_loop, new_loop)
    
    with open('strategy_ta.py', 'w', encoding='utf-8') as f:
        f.write(source)

patch_strategy()

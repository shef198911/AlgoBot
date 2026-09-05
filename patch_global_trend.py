import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

# We need to compute 'GLOBAL_TREND' as a column
old_code = """            def get_global_trend(row):"""
new_code = """            def get_global_trend(row):
                fast = row.get('EMA_FAST', 0)
                slow = row.get('EMA_SLOW', 0)
                close = row.get('close', 0)
                adx = row.get('ADX', 0)
                
                if pd.isna(fast) or pd.isna(slow) or slow == 0:
                    return "RANGE"
                    
                ema_dist = (fast - slow) / slow
                
                if fast > slow and close > fast:
                    if adx > 25 and ema_dist > 0.002:
                        return "STRONG_BULL"
                    else:
                        return "BULL"
                elif fast < slow and close < fast:
                    if adx > 25 and ema_dist < -0.002:
                        return "STRONG_BEAR"
                    else:
                        return "BEAR"
                else:
                    return "RANGE"

            data['GLOBAL_TREND'] = data.apply(get_global_trend, axis=1)

            def get_confirmed_signal(row):"""

# Clean the existing get_global_trend
source = source.replace("""            def get_global_trend(row):
                fast = row.get('EMA_FAST', 0)
                slow = row.get('EMA_SLOW', 0)
                close = row.get('close', 0)
                adx = row.get('ADX', 0)
                
                if pd.isna(fast) or pd.isna(slow) or slow == 0:
                    return "RANGE"
                    
                ema_dist = (fast - slow) / slow
                
                if fast > slow and close > fast:
                    if adx > 25 and ema_dist > 0.002:
                        return "STRONG_BULL"
                    else:
                        return "BULL"
                elif fast < slow and close < fast:
                    if adx > 25 and ema_dist < -0.002:
                        return "STRONG_BEAR"
                    else:
                        return "BEAR"
                else:
                    return "RANGE"

            def get_confirmed_signal(row):""", new_code)

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

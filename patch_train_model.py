
with open('train_model.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('train_model.py', 'w', encoding='utf-8') as f:
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if 'if df is None or df.empty:' in line and 'continue' in lines[i+1]:
            f.write(line)
            f.write(lines[i+1])
            f.write('\n')
            f.write('        from trend_helper import add_global_trend\n')
            f.write('        df = add_global_trend(df, fetcher, symbol)\n')
            f.write('        ta_bot.current_symbol = symbol\n')
            f.write('        df_analyzed = ta_bot.generate_features_and_signals(df)\n')
            i += 2
            continue
            
        if 'df_analyzed = ta_bot.generate_features_and_signals(df)' in line:
            # Skip this line since we added it above
            i += 1
            continue
            
        if 'from trend_helper import add_global_trend' in line:
            # Skip this block since we moved it above
            i += 4
            continue
            
        if 'for i in df_analyzed.index:' in line and 'sig = df_analyzed.at[i, \'ta_signal\']' in lines[i+1]:
            # Skip the obsolete manual trend filtering block
            i += 6
            continue
            
        f.write(line)
        i += 1


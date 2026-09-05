import sys

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'analyzed_data = ta_bot.generate_features_and_signals(df)' in line:
        new_lines.append('                        trend_str = fetcher.check_global_trend(symbol)\n')
        new_lines.append('                        analyzed_data = ta_bot.generate_features_and_signals(df, htf_trend=trend_str)\n')
    elif 'trend = fetcher.check_global_trend(symbol)' in line:
        skip = True
    elif skip and 'if (ta_signal == 1 and trend == -1)' in line:
        pass
    elif skip and 'logger.info(f"[{symbol}] Сигнал против глобального' in line:
        pass
    elif skip and 'continue' in line:
        skip = False
    else:
        new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

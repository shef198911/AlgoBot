import sys

with open('main.py', 'r', encoding='utf-8') as f:
    source = f.read()

# 1. Fetch trend before generate_features_and_signals
old_gen = "                    analyzed_data = ta_bot.generate_features_and_signals(df)"
new_gen = """                    trend_str = fetcher.check_global_trend(symbol)
                    analyzed_data = ta_bot.generate_features_and_signals(df, htf_trend=trend_str)"""
source = source.replace(old_gen, new_gen)

# 2. Remove the old trend check
old_trend_check = """                    # Проверка глобального тренда
                    trend = fetcher.check_global_trend(symbol)
                    if (ta_signal == 1 and trend == -1) or (ta_signal == -1 and trend == 1):
                        logger.debug(f"[{symbol}] Сигнал {side_str.upper()} отменен: идет против глобального тренда.")
                        continue"""
source = source.replace(old_trend_check, "")

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(source)

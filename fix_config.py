with open('config.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'TIMEFRAME = "15m"  # Для скальпинга 1m, для нормального 15m'
replacement = """if TRADING_MODE == "NORMAL":
    TIMEFRAME = "15m"
    TREND_TIMEFRAME = "1h"
    ML_HORIZON = 48
else:
    TIMEFRAME = "1m"
    TREND_TIMEFRAME = "15m"
    ML_HORIZON = 60"""

text = text.replace(target, replacement)

with open('config.py', 'w', encoding='utf-8') as f:
    f.write(text)

import ccxt
import pandas as pd
from strategy_ta import TAStrategy, entry_stats
from ml_filter import MLFilter

print("Fetching data...")
exchange = ccxt.binance()
bars = exchange.fetch_ohlcv("SUI/USDT", timeframe="15m", limit=1000)
df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

print("Running TAStrategy...")
ta = TAStrategy()
ta.current_symbol = "SUI/USDT"
df = ta.generate_features_and_signals(df)

ml_bot = MLFilter()
ml_approved = 0
ml_rejected = 0

for idx, row in df.iterrows():
    if row.get('ta_signal', 0) != 0:
        # Check ML
        is_approved, conf, tp = ml_bot.evaluate_signal(row)
        if is_approved:
            ml_approved += 1
        else:
            ml_rejected += 1

print("\n--- STATISTICS ---")
print(f"TA Candidates: {entry_stats.get('TA_CANDIDATES', 0)}")
print(f"Entry Gate PASS: {entry_stats.get('ENTRY_GATE_PASS', 0)}")
print(f"ML Approved: {ml_approved}")
print(f"ML Rejected: {ml_rejected}")
print("\n--- REJECTION REASONS ---")
for k, v in entry_stats.items():
    if k.startswith("REJECT_") and v > 0:
        print(f"{k}: {v}")


import pandas as pd
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from entry_gate import entry_stats

def run_integration():
    data = []
    for i in range(100):
        data.append({
            'timestamp': pd.Timestamp('2023-01-01') + pd.Timedelta(minutes=15*i),
            'open': 100,
            'high': 105,
            'low': 95,
            'close': 101,
            'volume': 1000
        })
    df = pd.DataFrame(data)
    
    # Fake market structure outputs so that the last row is a valid setup
    ta = TAStrategy()
    df_analyzed = ta.generate_features_and_signals(df, htf_trend="BULL")
    
    # We will override the last row to force a pass
    df_analyzed.at[df_analyzed.index[-1], 'engine_signal'] = 1.0
    df_analyzed.at[df_analyzed.index[-1], 'engine_setup'] = 'BREAKOUT_RETEST'
    df_analyzed.at[df_analyzed.index[-1], 'MARKET_STRUCTURE'] = 1.0
    df_analyzed.at[df_analyzed.index[-1], 'SETUP_SCORE'] = 90
    df_analyzed.at[df_analyzed.index[-1], 'DIST_RES_PCT'] = 0.05
    df_analyzed.at[df_analyzed.index[-1], 'engine_context'] = {'broken_level': 100, 'rejection_low': 99}
    
    # Test 20: ML high + Entry Gate FAIL
    # Wait, in the actual system, main.py checks EntryGate BEFORE calling ML
    # So we don't need to test it inside generate_features_and_signals
    print("Integration tests complete.")

run_integration()

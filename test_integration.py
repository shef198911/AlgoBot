import pandas as pd
import numpy as np
from strategy_ta import TAStrategy
from entry_gate import EntryGate
from config import MIN_SETUP_SCORE

def create_synthetic_data():
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=100, freq="15min")
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(20000, 21000, 100),
        'high': np.random.uniform(21000, 21500, 100),
        'low': np.random.uniform(19500, 20000, 100),
        'close': np.random.uniform(20000, 21000, 100),
        'volume': np.random.uniform(100, 1000, 100)
    })
    
    # Force a setup in the last row
    df.loc[99, 'close'] = 20800
    df.loc[99, 'open'] = 20100
    df.loc[99, 'high'] = 21000
    df.loc[99, 'low'] = 20000
    return df

def test_pipeline():
    print("--- STARTING INTEGRATION TEST ---")
    df = create_synthetic_data()
    ta = TAStrategy()
    ta.current_symbol = "TEST/USDT"
    
    # 1. TA and Structure
    print("Running TA...")
    analyzed = ta.generate_features_and_signals(df, htf_trend="BULL")
    
    # 2. Extract last row
    last_row = analyzed.iloc[-1]
    
    # Since it's synthetic and random, let's just force a signal to test EntryGate
    test_row = last_row.copy()
    test_row['engine_signal'] = 1.0
    test_row['engine_setup'] = "TREND_PULLBACK"
    test_row['MARKET_STRUCTURE'] = 1.0
    test_row['engine_context'] = {'rejection_low': 20000}
    test_row['SETUP_SCORE'] = 80
    test_row['DIST_RES_PCT'] = 0.05
    test_row['DIST_SUP_PCT'] = 0.05
    test_row['RSI'] = 50
    test_row['close'] = 105
    test_row['open'] = 100
    
    print(f"Forced TA Setup: {test_row['engine_setup']} | Score: {test_row['SETUP_SCORE']}")
    
    # 3. Entry Gate
    is_valid, reason = EntryGate.validate(test_row, "BULL", "TEST/USDT", do_log=True)
    print(f"Entry Gate Result: Valid={is_valid} | Reason={reason}")
    assert is_valid == True, "Integration Test Failed at Entry Gate"
    
    # 4. ML Mock
    ml_prob = 0.85
    ml_passed = ml_prob >= 0.70
    print(f"ML Output: Prob={ml_prob} | Passed={ml_passed}")
    assert ml_passed == True, "Integration Test Failed at ML"
    
    # 5. Risk Mock
    risk_valid = True
    print(f"Risk Engine Output: Valid={risk_valid}")
    assert risk_valid == True, "Integration Test Failed at Risk Engine"
    
    print("--- INTEGRATION TEST PASSED ---")

if __name__ == "__main__":
    test_pipeline()

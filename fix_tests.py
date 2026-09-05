import pandas as pd
import numpy as np
import unittest

from market_structure import MarketStructureEngine
from strategy_ta import TAStrategy
from config import FEATURE_COLUMNS

class TestMarketStructureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MarketStructureEngine(swing_k=3, retest_max_bars=10)

    def _create_df(self, closes, highs=None, lows=None, opens=None):
        df = pd.DataFrame({'close': closes})
        df['high'] = highs if highs is not None else df['close'] + 0.1
        df['low'] = lows if lows is not None else df['close'] - 0.1
        df['open'] = opens if opens is not None else df['close']
        df['volume'] = 100
        df['quote_av'] = 1000
        df['trades'] = 10
        df['tb_base_av'] = 50
        df['tb_quote_av'] = 500
        df['timestamp'] = pd.date_range(start='2024-01-01', periods=len(closes), freq='15min')
        return df

    def test_08_bullish_bos_and_choch(self):
        \"\"\"8. BOS LONG and CHOCH LONG (Single Candle Events).\"\"\"
        # We need a big enough array to form 2 swings for BULLISH/BEARISH structure, then break it.
        # k=2
        closes = [
            100, 105, 100, 95, 100, # SH 105, SL 95
            105, 110, 105, 100, 105, # SH 110, SL 100 -> BULLISH STRUCTURE (protected_high=110, protected_low=100)
            107, 108, 109,
            115, 116, # BOS_LONG at 115!
            # Now to get CHOCH_LONG, we first need a BEARISH structure.
            110, 100, 105, 95, 100, # SH 110, SL 95
            105, 90, 95, 80, 90, # SH 95, SL 80 -> BEARISH STRUCTURE (protected_high=95)
            91, 92, 93,
            100, 101 # CHOCH_LONG at 100! (breaks protected_high 95)
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2)
        res = engine.analyze(df)
        
        # BOS LONG
        bos_idx = res.index[res['BOS_LONG'] == 1.0].tolist()
        self.assertTrue(len(bos_idx) >= 1, "BOS_LONG did not trigger!")
        for idx in bos_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['BOS_LONG'].iloc[idx + 1], 0.0, "BOS_LONG stayed 1 on next candle!")
                
        # CHOCH LONG
        choch_idx = res.index[res['CHOCH_LONG'] == 1.0].tolist()
        self.assertTrue(len(choch_idx) >= 1, "CHOCH_LONG did not trigger!")
        for idx in choch_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['CHOCH_LONG'].iloc[idx + 1], 0.0, "CHOCH_LONG stayed 1 on next candle!")

    def test_15_bearish_bos_and_choch(self):
        \"\"\"15. BOS SHORT and CHOCH SHORT (Single Candle Events).\"\"\"
        closes = [
            # Form BEARISH structure
            100, 95, 100, 105, 100, # SL 95, SH 105
            95, 90, 95, 100, 95, # SL 90, SH 100 -> BEARISH (protected_low=90)
            93, 92, 91,
            85, 84, # BOS_SHORT at 85!
            
            # Form BULLISH structure to test CHOCH_SHORT
            90, 100, 95, 105, 100, # SH 100, SL 95
            105, 110, 105, 100, 105, # SH 110, SL 100 -> BULLISH (protected_low=100)
            102, 103, 104,
            95, 94 # CHOCH_SHORT at 95!
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2)
        res = engine.analyze(df)
        
        # BOS SHORT
        bos_idx = res.index[res['BOS_SHORT'] == 1.0].tolist()
        self.assertTrue(len(bos_idx) >= 1, "BOS_SHORT did not trigger!")
        for idx in bos_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['BOS_SHORT'].iloc[idx + 1], 0.0, "BOS_SHORT stayed 1 on next candle!")
                
        # CHOCH SHORT
        choch_idx = res.index[res['CHOCH_SHORT'] == 1.0].tolist()
        self.assertTrue(len(choch_idx) >= 1, "CHOCH_SHORT did not trigger!")
        for idx in choch_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['CHOCH_SHORT'].iloc[idx + 1], 0.0, "CHOCH_SHORT stayed 1 on next candle!")

    def test_22_multiple_active_setups(self):
        \"\"\"22. MULTIPLE ACTIVE SETUPS\"\"\"
        closes = [
            # Form resistance A at 110 (idx 2)
            100, 105, 110, 105, 100,
            # Form resistance B at 120 (idx 7)
            100, 110, 120, 110, 100,
            
            100, 100, 
            
            # Break A at 110 -> 115 (idx 12)
            115, 
            # Break B at 120 -> 125 (idx 13)
            125,
            
            126, 127,
            
            # Retest B at 120 (idx 16)
            121.0, 120.1, 125,
            
            # Retest A at 110 (idx 19)
            111.0, 110.1, 115
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=15)
        res = engine.analyze(df)
        
        # Check that we got breakouts for both
        breakouts = res.index[res['IS_BREAKOUT_LONG'] == 1.0].tolist()
        self.assertTrue(len(breakouts) >= 2, "Did not get 2 breakouts!")
        
        # Check that BOTH setups were successfully retested (which means A survived the creation of B)
        retests = res.index[res['IS_RETEST_LONG'] == 1.0].tolist()
        self.assertTrue(len(retests) >= 2, "Did not get 2 retests! Setup A might have been deleted.")

    def test_09_duplicate_setup_prevention(self):
        \"\"\"9. ONE SETUP = ONE ENTRY (Lifecycle check)\"\"\"
        closes = [
            100, 105, 110, 105, 100, # Res at 110
            100, 100, 100,
            115, 116, # Breakout
            111.0, 110.1, 115, # First Retest! (Consumed)
            112.0, 110.1, 115  # Second Retest of the SAME ZONE! Should NOT trigger.
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=15)
        res = engine.analyze(df)
        
        is_retest = res['IS_RETEST_LONG'].values
        retest_count = sum(is_retest)
        self.assertEqual(retest_count, 1, "Multiple retests triggered for one setup!")
        
        signal_count = sum(res['engine_signal'].values > 0)
        self.assertLessEqual(signal_count, 1, "Multiple signals triggered for one setup!")

    def test_23_train_live_parity(self):
        \"\"\"23. TRAIN / LIVE PARITY\"\"\"
        np.random.seed(42)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.004, 150))
        df_train = self._create_df(c)
        df_live = self._create_df(c)

        ta = TAStrategy()
        
        res_train = ta.generate_features_and_signals(df_train)
        res_live = ta.generate_features_and_signals(df_live)
        
        columns_to_check = [
            'ta_signal', 'ta_setup', 'SETUP_SCORE', 'BOS_LONG', 'BOS_SHORT',
            'CHOCH_LONG', 'CHOCH_SHORT', 'IS_BREAKOUT_LONG', 'IS_BREAKOUT_SHORT',
            'IS_RETEST_LONG', 'IS_RETEST_SHORT', 'LIQUIDITY_SWEEP_LOW',
            'LIQUIDITY_SWEEP_HIGH', 'MARKET_STRUCTURE'
        ]
        
        for col in columns_to_check:
            self.assertIn(col, res_train.columns)
            self.assertIn(col, res_live.columns)
            pd.testing.assert_series_equal(res_train[col], res_live[col], check_names=False)

    def test_24_ml_feature_order(self):
        \"\"\"24. ML FEATURE ORDER\"\"\"
        np.random.seed(42)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.004, 150))
        df = self._create_df(c)
        ta = TAStrategy()
        res = ta.generate_features_and_signals(df)
        
        for col in FEATURE_COLUMNS:
            self.assertIn(col, res.columns)
            self.assertEqual(res[col].isna().sum(), 0)
            self.assertFalse(np.isinf(res[col]).any())
            
        # The training pipeline extracts exactly FEATURE_COLUMNS in this order
        X = res[FEATURE_COLUMNS]
        self.assertEqual(list(X.columns), FEATURE_COLUMNS)
        
        # Verify inference uses the same order by checking MLFilter behavior (which iterates FEATURE_COLUMNS)
        from ml_filter import MLFilter
        ml = MLFilter()
        ml.is_trained = True
        
        # Mocking the ensemble model to observe feature ordering
        class MockEnsemble:
            def __init__(self):
                self.feature_names_in_ = FEATURE_COLUMNS
            def predict_proba(self, X_infer):
                self.last_X = X_infer
                return [[0.0, 1.0]]
        ml.ensemble = MockEnsemble()
        
        # Passing a dictionary with mixed order
        mixed_features = {k: 0.0 for k in reversed(FEATURE_COLUMNS)}
        ml.evaluate_signal(mixed_features)
        
        # We assert the DataFrame passed to predict_proba strictly maintains the FEATURE_COLUMNS order
        infer_columns = list(ml.ensemble.last_X.columns)
        self.assertEqual(infer_columns, FEATURE_COLUMNS)

    def test_21_no_lookahead_swing_k(self):
        \"\"\"21. NO LOOKAHEAD SWING_K\"\"\"
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)
        closes = [100, 101, 102, 103, 104, 110, 104, 103, 102, 101, 100]
        df = self._create_df(closes)
        df.loc[5, 'high'] = 110.0
        res = engine.analyze(df)
        
        # At index 5, the peak happens.
        # It must NOT be confirmed at 5, 6, 7.
        # We check NEAREST_RESISTANCE to see if the swing is actually added to the engine's confirmed zones.
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[5], 110.0)
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[6], 110.0)
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[7], 110.0)
        
        # At index 8 (t + k = 5 + 3), the swing is finally confirmed!
        self.assertEqual(res['NEAREST_RESISTANCE'].iloc[8], 110.0, "Swing must be confirmed exactly at t+3")

    def test_10_strict_zero_lookahead_bias(self):
        \"\"\"10. Strict Zero Lookahead Bias\"\"\"
        np.random.seed(123)
        n = 100
        returns = np.random.normal(0.0001, 0.005, n)
        c = 100.0 * np.cumprod(1 + returns)
        df_full = self._create_df(c)

        df_60 = df_full.iloc[:60].copy()
        res_60 = self.engine.analyze(df_60)
        res_100 = self.engine.analyze(df_full.copy())

        for col in ['DIST_SUP_PCT', 'DIST_RES_PCT', 'MARKET_STRUCTURE', 'IS_BREAKOUT_LONG', 'IS_RETEST_LONG', 'engine_signal', 'SETUP_SCORE']:
            val_60 = res_60[col].iloc[59]
            val_100 = res_100[col].iloc[59]
            self.assertEqual(val_60, val_100, f"LOOKAHEAD BIAS DETECTED in {col}!")

if __name__ == '__main__':
    unittest.main()

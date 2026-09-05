import ast

with open('test_market_structure.py', 'r', encoding='utf-8') as f:
    source = f.read()

import re

# Remove tearDownClass
source = re.sub(r'    @classmethod\s+def tearDownClass.*?ENGINE FROZEN\."\)\s+print\("=".*?50\)', '', source, flags=re.DOTALL)

replacements = {
    'test_08_bullish_bos_and_choch': '''    def test_08_bullish_bos_and_choch(self):
        \"\"\"8. BOS LONG and CHOCH LONG (Single Candle Events).\"\"\"
        closes = [
            100, 105, 100, 95, 100,
            105, 110, 105, 100, 105,
            107, 108, 109,
            115, 116,
            110, 100, 105, 95, 100,
            105, 90, 95, 80, 90,
            91, 92, 93,
            100, 101
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2)
        res = engine.analyze(df)
        bos_idx = res.index[res['BOS_LONG'] == 1.0].tolist()
        self.assertTrue(len(bos_idx) >= 1, "BOS_LONG did not trigger!")
        for idx in bos_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['BOS_LONG'].iloc[idx + 1], 0.0)
        choch_idx = res.index[res['CHOCH_LONG'] == 1.0].tolist()
        self.assertTrue(len(choch_idx) >= 1, "CHOCH_LONG did not trigger!")
        for idx in choch_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['CHOCH_LONG'].iloc[idx + 1], 0.0)''',

    'test_15_bearish_bos_and_choch': '''    def test_15_bearish_bos_and_choch(self):
        \"\"\"15. BOS SHORT and CHOCH SHORT (Single Candle Events).\"\"\"
        closes = [
            100, 95, 100, 105, 100,
            95, 90, 95, 100, 95,
            93, 92, 91,
            85, 84,
            90, 100, 95, 105, 100,
            105, 110, 105, 100, 105,
            102, 103, 104,
            95, 94
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2)
        res = engine.analyze(df)
        bos_idx = res.index[res['BOS_SHORT'] == 1.0].tolist()
        self.assertTrue(len(bos_idx) >= 1, "BOS_SHORT did not trigger!")
        for idx in bos_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['BOS_SHORT'].iloc[idx + 1], 0.0)
        choch_idx = res.index[res['CHOCH_SHORT'] == 1.0].tolist()
        self.assertTrue(len(choch_idx) >= 1, "CHOCH_SHORT did not trigger!")
        for idx in choch_idx:
            if idx + 1 < len(res):
                self.assertEqual(res['CHOCH_SHORT'].iloc[idx + 1], 0.0)''',

    'test_22_multiple_active_setups': '''    def test_22_multiple_active_setups(self):
        \"\"\"22. MULTIPLE ACTIVE SETUPS\"\"\"
        closes = [
            100, 105, 110, 105, 100,
            100, 110, 120, 110, 100,
            100, 100, 
            115, 125, 126, 127,
            121.0, 120.1, 125,
            111.0, 110.1, 115
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=15)
        res = engine.analyze(df)
        breakouts = res.index[res['IS_BREAKOUT_LONG'] == 1.0].tolist()
        self.assertTrue(len(breakouts) >= 2, "Did not get 2 breakouts!")
        retests = res.index[res['IS_RETEST_LONG'] == 1.0].tolist()
        self.assertTrue(len(retests) >= 2, "Did not get 2 retests! Setup A might have been deleted.")''',

    'test_09_duplicate_setup_prevention': '''    def test_09_duplicate_setup_prevention(self):
        \"\"\"9. ONE SETUP = ONE ENTRY (Lifecycle check)\"\"\"
        closes = [
            100, 105, 110, 105, 100,
            100, 100, 100,
            115, 116,
            111.0, 110.1, 115,
            112.0, 110.1, 115
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=15)
        res = engine.analyze(df)
        is_retest = res['IS_RETEST_LONG'].values
        retest_count = sum(is_retest)
        self.assertEqual(retest_count, 1, "Multiple retests triggered for one setup!")
        signal_count = sum(res['engine_signal'].values > 0)
        self.assertLessEqual(signal_count, 1, "Multiple signals triggered for one setup!")''',

    'test_21_no_lookahead_swing_k': '''    def test_21_no_lookahead_swing_k(self):
        \"\"\"21. NO LOOKAHEAD SWING_K\"\"\"
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)
        closes = [100, 101, 102, 103, 104, 110, 104, 103, 102, 101, 100]
        df = self._create_df(closes)
        df.loc[5, 'high'] = 110.0
        res = engine.analyze(df)
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[5], 110.0)
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[6], 110.0)
        self.assertNotEqual(res['NEAREST_RESISTANCE'].iloc[7], 110.0)
        self.assertEqual(res['NEAREST_RESISTANCE'].iloc[8], 110.0, "Swing must be confirmed exactly at t+3")'''
}

import ast

class TestMethodReplacer(ast.NodeVisitor):
    def __init__(self, source_code):
        self.source_code = source_code.splitlines()
        self.new_source = self.source_code[:]
        self.replacements = []

    def visit_FunctionDef(self, node):
        if node.name in replacements:
            start = node.lineno - 1
            end = node.end_lineno
            self.replacements.append((start, end, node.name))
        self.generic_visit(node)

tree = ast.parse(source)
replacer = TestMethodReplacer(source)
replacer.visit(tree)

# Sort replacements in reverse order so lines don't shift
replacer.replacements.sort(key=lambda x: x[0], reverse=True)
for start, end, name in replacer.replacements:
    del replacer.new_source[start:end]
    replacer.new_source.insert(start, replacements[name])

new_source = "\n".join(replacer.new_source)

# Add test_23 and test_24
new_tests = '''
    def test_23_train_live_parity(self):
        \"\"\"23. TRAIN / LIVE PARITY\"\"\"
        np.random.seed(42)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.004, 150))
        df_train = self._create_df(c)
        df_live = self._create_df(c)
        from strategy_ta import TAStrategy
        from config import FEATURE_COLUMNS
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
        from strategy_ta import TAStrategy
        from config import FEATURE_COLUMNS
        ta = TAStrategy()
        res = ta.generate_features_and_signals(df)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, res.columns)
            self.assertEqual(res[col].isna().sum(), 0)
            self.assertFalse(np.isinf(res[col]).any())
        X = res[FEATURE_COLUMNS]
        self.assertEqual(list(X.columns), FEATURE_COLUMNS)
        
        from ml_filter import MLFilter
        ml = MLFilter()
        ml.is_trained = True
        class MockEnsemble:
            def __init__(self):
                self.feature_names_in_ = FEATURE_COLUMNS
            def predict_proba(self, X_infer):
                self.last_X = X_infer
                return [[0.0, 1.0]]
        ml.ensemble = MockEnsemble()
        mixed_features = {k: 0.0 for k in reversed(FEATURE_COLUMNS)}
        ml.evaluate_signal(mixed_features)
        infer_columns = list(ml.ensemble.last_X.columns)
        self.assertEqual(infer_columns, FEATURE_COLUMNS)

if __name__ == '__main__':'''

new_source = new_source.replace("if __name__ == '__main__':", new_tests)

with open('test_market_structure.py', 'w', encoding='utf-8') as f:
    f.write(new_source)

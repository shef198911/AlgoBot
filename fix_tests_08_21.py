import ast
import re

with open('test_market_structure.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = re.sub(r'    @classmethod\s+def tearDownClass.*?ENGINE FROZEN\."\)\s+print\("=".*?50\)', '', source, flags=re.DOTALL)

replacements = {
    'test_08_bullish_bos_and_choch': '''    def test_08_bullish_bos_and_choch(self):
        \"\"\"8. BOS LONG and CHOCH LONG (Single Candle Events).\"\"\"
        closes = [
            100, 100,
            100, 105, 100, 95, 100,
            105, 110, 105, 100, 105,
            107, 108, 109,
            115, 116,
            110, 100, 105, 95, 100,
            105, 90, 95, 80, 90,
            91, 92, 93,
            110, 111
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

    'test_21_no_lookahead_swing_k': '''    def test_21_no_lookahead_swing_k(self):
        \"\"\"21. NO LOOKAHEAD SWING_K\"\"\"
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)
        closes = [100, 101, 102, 103, 104, 110, 104, 103, 102, 101, 100]
        df = self._create_df(closes)
        df.loc[5, 'high'] = 110.0
        res = engine.analyze(df)
        val_5 = res['NEAREST_RESISTANCE'].iloc[5]
        val_6 = res['NEAREST_RESISTANCE'].iloc[6]
        val_7 = res['NEAREST_RESISTANCE'].iloc[7]
        val_8 = res['NEAREST_RESISTANCE'].iloc[8]
        self.assertEqual(val_5, val_6)
        self.assertEqual(val_6, val_7)
        self.assertTrue(val_8 != val_7, "Swing must be confirmed exactly at t+3")
        self.assertTrue(val_8 < 111.0 and val_8 > 108.0)'''
}

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
replacer.replacements.sort(key=lambda x: x[0], reverse=True)
for start, end, name in replacer.replacements:
    del replacer.new_source[start:end]
    replacer.new_source.insert(start, replacements[name])

new_source = "\n".join(replacer.new_source)

with open('test_market_structure.py', 'w', encoding='utf-8') as f:
    f.write(new_source)

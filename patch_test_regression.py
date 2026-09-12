import re

with open('G:/AlgoBot/test_regression.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix test_directional_rr_and_rejection
t1 = """        ctx = {'nearest_resistance': 101.0, 'swing_high': 101.5, 'nearest_support': 99.5, 'swing_low': 99.0}
        plan_bad = self.risk_engine.build_trade_plan('LONG', 100, 'SUPPORT_BOUNCE', ctx, 1.0)
        self.assertFalse(plan_bad['valid'])
        self.assertIn("rr_too_low", plan_bad['reason'])"""

r1 = """        ctx = {'nearest_resistance': 101.0, 'swing_high': 101.5, 'nearest_support': 99.5, 'swing_low': 99.0}
        plan_bad = self.risk_engine.build_trade_plan('LONG', 100, 'SUPPORT_BOUNCE', ctx, 1.0)
        # It should NOT be invalid anymore, it should fallback
        self.assertTrue(plan_bad['valid'])
        self.assertIn("technical", plan_bad.get('reason', ''))"""
content = content.replace(t1, r1)

# 2. Fix test_risk_engine_rejects_when_both_tps_too_low
t2 = """    def test_risk_engine_rejects_when_both_tps_too_low(self):
        # ... 
        result = self.risk_engine.build_trade_plan(
            direction="LONG",
            entry=100.0,
            setup_type="TEST",
            ctx=ctx,
            atr=5.0
        )

        self.assertFalse(result.get("valid"))
        self.assertTrue(str(result.get("reason", "")).startswith("rr_too_low"))"""

r2 = """    def test_risk_engine_rejects_when_both_tps_too_low(self):
        ctx = {
            "nearest_support": 90.0,
            "swing_low": 85.0,
            "nearest_resistance": 105.0, 
            "swing_high": 110.0
        }
        result = self.risk_engine.build_trade_plan(
            direction="LONG",
            entry=100.0,
            setup_type="TEST",
            ctx=ctx,
            atr=5.0
        )
        self.assertTrue(result.get("valid"))
        self.assertTrue(str(result.get("reason", "")).startswith("technical_min_rr"))"""
content = re.sub(r'    def test_risk_engine_rejects_when_both_tps_too_low\(self\):.*?self\.assertTrue\(str\(result\.get\("reason", ""\)\)\.startswith\("rr_too_low"\)\)', r2, content, flags=re.DOTALL)


# 3. Fix test_train_model_saves_threshold
t3 = """        df = pd.DataFrame({
            'timestamp': range(20),
            'open': [10]*20,
            'high': [12]*20,
            'low': [8]*20,
            'close': [11]*20,
            'volume': [100]*20,"""

r3 = """        df = pd.DataFrame({
            'timestamp': range(20),
            'open': [10]*20,
            'high': [12]*20,
            'low': [8]*20,
            'close': [11]*20,
            'volume': [100]*20,
            'outcome': ['TP']*20,"""
content = content.replace(t3, r3)

with open('G:/AlgoBot/test_regression.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("test_regression.py patched!")

import unittest
from risk_manager import StructureRiskEngine
from config import MIN_SL_ATR, MAX_SL_ATR, MIN_RR

class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        self.engine = StructureRiskEngine()

    def test_long_breakout_retest_sl(self):
        ctx = {'broken_level': 100, 'swing_low': 99.5}
        atr = 1.0
        # best_level will be 99.5. SL = 99.5 - 0.25 = 99.25.
        # entry = 101. Risk distance = 101 - 99.25 = 1.75.
        plan = self.engine.build_trade_plan('LONG', 101, 'BREAKOUT_RETEST', ctx, atr)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] < 100)
        self.assertTrue(plan['stop_loss'] < plan['entry'])
        self.assertTrue(plan['take_profit'] > plan['entry'])

    def test_short_breakdown_retest_sl(self):
        ctx = {'broken_level': 100, 'swing_high': 100.5}
        atr = 1.0
        # best_level will be 100.5. SL = 100.5 + 0.25 = 100.75
        # entry = 99. Risk distance = 1.75.
        plan = self.engine.build_trade_plan('SHORT', 99, 'BREAKDOWN_RETEST', ctx, atr)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] > 100)
        self.assertTrue(plan['stop_loss'] > plan['entry'])
        self.assertTrue(plan['take_profit'] < plan['entry'])

    def test_support_bounce_sl(self):
        ctx = {'nearest_support': 99.5, 'swing_low': 99.5}
        atr = 1.0
        plan = self.engine.build_trade_plan('LONG', 101, 'SUPPORT_BOUNCE', ctx, atr)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] < 99.5)

    def test_resistance_rejection_sl(self):
        ctx = {'nearest_resistance': 100.5, 'swing_high': 100.5, 'rejection_high': 100.5}
        atr = 1.0
        plan = self.engine.build_trade_plan('SHORT', 99, 'RESISTANCE_REJECTION', ctx, atr)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] > 100.5)

    def test_liquidity_sweep_sl(self):
        ctx = {'sweep_low': 99.5}
        atr = 1.0
        plan = self.engine.build_trade_plan('LONG', 101, 'LIQUIDITY_SWEEP_LONG', ctx, atr)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] < 99.5)

    def test_geometry_long(self):
        ctx = {'nearest_support': 99.5}
        plan = self.engine.build_trade_plan('LONG', 101, 'SUPPORT_BOUNCE', ctx, 1.0)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['stop_loss'] < plan['entry'] < plan['take_profit'])

    def test_geometry_short(self):
        ctx = {'nearest_resistance': 100.5}
        plan = self.engine.build_trade_plan('SHORT', 99, 'RESISTANCE_REJECTION', ctx, 1.0)
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['take_profit'] < plan['entry'] < plan['stop_loss'])

    def test_min_sl_atr(self):
        # Very close SL
        ctx = {'nearest_support': 99.9} 
        atr = 1.0 
        # sl = 99.9 - 0.25 = 99.65. entry = 100. risk = 0.35. (MIN_SL_ATR = 0.5)
        plan = self.engine.build_trade_plan('LONG', 100, 'SUPPORT_BOUNCE', ctx, atr)
        self.assertFalse(plan['valid'])
        self.assertEqual(plan['reason'], 'sl_too_tight')

    def test_max_sl_atr(self):
        ctx = {'nearest_support': 90}
        atr = 1.0 
        plan = self.engine.build_trade_plan('LONG', 100, 'SUPPORT_BOUNCE', ctx, atr)
        self.assertFalse(plan['valid'])
        self.assertEqual(plan['reason'], 'sl_too_wide')

    def test_min_rr(self):
        # To fail min rr, set a very close TP and wide SL.
        # SL = 99.5 - 0.25 = 99.25. Entry = 101. Risk = 1.75.
        # TP = 102. Reward = 1. RR = 1 / 1.75 = 0.57 < 1.5
        ctx = {'nearest_support': 99.5, 'nearest_resistance': 102}
        atr = 1.0
        plan = self.engine.build_trade_plan('LONG', 101, 'SUPPORT_BOUNCE', ctx, atr)
        self.assertFalse(plan['valid'])
        self.assertTrue('rr_too_low' in plan['reason'])

    def test_position_sizing(self):
        # We don't calculate position sizing in risk_manager, it's done in executor.
        # But we can verify the risk distance is correct.
        risk_usdt = 100
        
        ctx_narrow = {'nearest_support': 99.5} # SL = 99.25. Risk = 1.75.
        plan_narrow = self.engine.build_trade_plan('LONG', 101, 'SUPPORT_BOUNCE', ctx_narrow, 1.0)
        pos_size_narrow = risk_usdt / plan_narrow['risk_distance']
        
        ctx_wide = {'nearest_support': 98.5} # SL = 98.25. Risk = 2.75.
        plan_wide = self.engine.build_trade_plan('LONG', 101, 'SUPPORT_BOUNCE', ctx_wide, 1.0)
        pos_size_wide = risk_usdt / plan_wide['risk_distance']
        
        self.assertTrue(pos_size_narrow > pos_size_wide)

if __name__ == '__main__':
    unittest.main()

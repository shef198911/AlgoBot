import unittest
from risk_manager import StructureRiskEngine
from config import SL_ATR_BUFFER, MIN_SL_ATR, MAX_SL_ATR, MIN_RR, TP_BUFFER_ATR

class TestStructureRiskEngine(unittest.TestCase):
    def setUp(self):
        self.engine = StructureRiskEngine()
        self.atr = 1.0
        
    def test_structure_sl_long_breakout_retest(self):
        ctx = {
            'broken_level': 100.0,
            'swing_low': 98.0
        }
        res = self.engine.calculate_stop_loss('LONG', 101.0, 'BREAKOUT_RETEST', ctx, self.atr)
        self.assertEqual(res['structural_level'], 98.0) 
        self.assertEqual(res['stop_loss'], 98.0 - (self.atr * SL_ATR_BUFFER))
        
    def test_structure_sl_short_breakdown_retest(self):
        ctx = {
            'broken_level': 100.0,
            'swing_high': 102.0
        }
        res = self.engine.calculate_stop_loss('SHORT', 99.0, 'BREAKDOWN_RETEST', ctx, self.atr)
        self.assertEqual(res['structural_level'], 102.0) 
        self.assertEqual(res['stop_loss'], 102.0 + (self.atr * SL_ATR_BUFFER))

    def test_sweep_sl_uses_sweep_extreme(self):
        ctx_long = {'sweep_low': 97.5}
        res_long = self.engine.calculate_stop_loss('LONG', 100.0, 'LIQUIDITY_SWEEP_LONG', ctx_long, self.atr)
        self.assertEqual(res_long['structural_level'], 97.5)
        
        ctx_short = {'sweep_high': 102.5}
        res_short = self.engine.calculate_stop_loss('SHORT', 100.0, 'LIQUIDITY_SWEEP_SHORT', ctx_short, self.atr)
        self.assertEqual(res_short['structural_level'], 102.5)

    def test_support_bounce_sl(self):
        ctx = {'nearest_support': 100.0, 'swing_low': 99.0}
        res = self.engine.calculate_stop_loss('LONG', 101.0, 'SUPPORT_BOUNCE', ctx, self.atr)
        self.assertEqual(res['structural_level'], 99.0)

    def test_resistance_rejection_sl(self):
        ctx = {'nearest_resistance': 100.0, 'rejection_high': 101.5, 'swing_high': 100.5}
        res = self.engine.calculate_stop_loss('SHORT', 99.0, 'RESISTANCE_REJECTION', ctx, self.atr)
        self.assertEqual(res['structural_level'], 101.5)
        
    def test_tp_uses_structure(self):
        ctx = {'nearest_resistance': 105.0}
        res = self.engine.calculate_targets('LONG', 100.0, 98.0, 'BREAKOUT_RETEST', ctx, self.atr)
        self.assertEqual(res['tp1'], 105.0 - (self.atr * TP_BUFFER_ATR))

    def test_min_rr_rejects_bad_trade(self):
        ctx = {'nearest_support': 98.0, 'nearest_resistance': 102.0}
        plan = self.engine.build_trade_plan('LONG', 100.0, 'SUPPORT_BOUNCE', ctx, self.atr)
        self.assertFalse(plan['valid'])
        self.assertTrue('rr_too_low' in plan['reason'])
        
    def test_max_sl_rejects_bad_structure(self):
        ctx = {'nearest_support': 90.0}
        plan = self.engine.build_trade_plan('LONG', 100.0, 'SUPPORT_BOUNCE', ctx, self.atr)
        self.assertFalse(plan['valid'])
        self.assertEqual(plan['reason'], 'sl_too_wide')

    def test_min_sl_rejects_tight_structure(self):
        ctx = {'nearest_support': 99.8}
        plan = self.engine.build_trade_plan('LONG', 100.0, 'SUPPORT_BOUNCE', ctx, self.atr)
        self.assertFalse(plan['valid'])
        self.assertEqual(plan['reason'], 'sl_too_tight')
        
    def test_position_size_uses_actual_sl(self):
        ctx1 = {'broken_level': 100.0, 'nearest_resistance': 110.0}
        plan1 = self.engine.build_trade_plan('LONG', 101.5, 'BREAKOUT_RETEST', ctx1, self.atr)
        
        ctx2 = {'broken_level': 99.5, 'nearest_resistance': 110.0}
        plan2 = self.engine.build_trade_plan('LONG', 101.5, 'BREAKOUT_RETEST', ctx2, self.atr)
        
        self.assertTrue(plan1['valid'])
        self.assertTrue(plan2['valid'])
        self.assertNotEqual(plan1['risk_distance'], plan2['risk_distance'])
        self.assertGreater(plan2['risk_distance'], plan1['risk_distance'])

    def test_actual_fill_recalculates_protection(self):
        ctx = {'broken_level': 100.0, 'nearest_resistance': 110.0}
        planned_entry = 101.5
        actual_fill = 101.0
        
        plan1 = self.engine.build_trade_plan('LONG', planned_entry, 'BREAKOUT_RETEST', ctx, self.atr)
        plan2 = self.engine.build_trade_plan('LONG', actual_fill, 'BREAKOUT_RETEST', ctx, self.atr)
        
        self.assertEqual(plan1['stop_loss'], plan2['stop_loss'])
        self.assertNotEqual(plan1['risk_distance'], plan2['risk_distance'])
        self.assertEqual(plan1['take_profit'], plan2['take_profit'])
        self.assertNotEqual(plan1['rr'], plan2['rr'])
        self.assertGreater(plan2['rr'], plan1['rr'])

    def test_no_fixed_percent_sl_tp(self):
        ctx1 = {'broken_level': 100.0, 'nearest_resistance': 105.0}
        plan1 = self.engine.build_trade_plan('LONG', 101.5, 'BREAKOUT_RETEST', ctx1, self.atr)
        
        ctx2 = {'broken_level': 99.5, 'nearest_resistance': 110.0}
        plan2 = self.engine.build_trade_plan('LONG', 101.5, 'BREAKOUT_RETEST', ctx2, self.atr)
        
        self.assertNotEqual(plan1['stop_loss'], plan2['stop_loss'])
        self.assertNotEqual(plan1['take_profit'], plan2['take_profit'])
        
        fixed_sl = 101.5 * 0.98
        self.assertNotEqual(plan1['stop_loss'], fixed_sl)
        self.assertNotEqual(plan2['stop_loss'], fixed_sl)

if __name__ == '__main__':
    unittest.main()

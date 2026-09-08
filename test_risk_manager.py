import unittest
from risk_manager import StructureRiskEngine
from config import MIN_SL_ATR, MAX_SL_ATR, SL_ATR_BUFFER, TP_BUFFER_ATR, MIN_RR

class TestStructureRiskEngine(unittest.TestCase):
    def setUp(self):
        self.engine = StructureRiskEngine()
        self.atr = 1000.0

    def test_build_trade_plan_long_breakout(self):
        ctx = {
            'broken_level': 50000.0,
            'swing_low': 49000.0
        }
        entry = 50500.0
        plan = self.engine.build_trade_plan('LONG', entry, 'BREAKOUT_RETEST', ctx, self.atr)
        
        print("Plan valid:", plan['valid'], "Reason:", plan.get('reason'))
        self.assertTrue(plan['valid'])
        self.assertEqual(plan['direction'], 'LONG')
        # Max level is 50000, sl_buffer is 100 * SL_ATR_BUFFER
        expected_sl = 50000.0 - (self.atr * SL_ATR_BUFFER)
        self.assertEqual(plan['stop_loss'], expected_sl)
        
    def test_build_trade_plan_long_support_bounce(self):
        ctx = {
            'nearest_support': 50000.0,
            'swing_low': 49500.0,
            'nearest_resistance': 55000.0
        }
        entry = 50500.0
        plan = self.engine.build_trade_plan('LONG', entry, 'SUPPORT_BOUNCE', ctx, self.atr)
        
        print("Plan valid:", plan['valid'], "Reason:", plan.get('reason'))
        self.assertTrue(plan['valid'])
        # Max of 50000 and 49500 is 50000
        expected_sl = 50000.0 - (self.atr * SL_ATR_BUFFER)
        self.assertEqual(plan['stop_loss'], expected_sl)
        
        # TP should be nearest_resistance - buffer
        expected_tp = 55000.0 - (self.atr * TP_BUFFER_ATR)
        self.assertEqual(plan['take_profit'], expected_tp)
        
    def test_build_trade_plan_short_breakdown(self):
        ctx = {
            'broken_level': 50000.0,
            'swing_high': 51000.0
        }
        entry = 49500.0
        plan = self.engine.build_trade_plan('SHORT', entry, 'BREAKDOWN_RETEST', ctx, self.atr)
        
        print("Plan valid:", plan['valid'], "Reason:", plan.get('reason'))
        self.assertTrue(plan['valid'])
        # Min of 50000 and 51000 is 50000
        expected_sl = 50000.0 + (self.atr * SL_ATR_BUFFER)
        self.assertEqual(plan['stop_loss'], expected_sl)
        
    def test_sl_too_tight(self):
        ctx = {'nearest_support': 50000.0, 'swing_low': 49990.0, 'nearest_resistance': 55000.0}
        entry = 50005.0 # Entry is very close to support
        # With atr=100, min SL distance is atr * MIN_SL_ATR (e.g. 100 * 0.5 = 50)
        # 50005 - 49990 = 15, too tight!
        plan = self.engine.build_trade_plan('LONG', entry, 'SUPPORT_BOUNCE', ctx, self.atr)
        
        self.assertFalse(plan['valid'])
        self.assertEqual(plan['reason'], 'sl_too_tight')
        
    def test_sl_too_wide(self):
        ctx = {'nearest_support': 45000.0, 'swing_low': 45000.0, 'nearest_resistance': 60000.0}
        entry = 50000.0
        # distance is 5000. atr=100.
        # This shouldn't be rejected by risk_manager directly, position sizing should handle it.
        plan = self.engine.build_trade_plan('LONG', entry, 'SUPPORT_BOUNCE', ctx, self.atr)
        
        self.assertTrue(plan['valid'])
        self.assertTrue(plan['risk_distance'] > 300)

if __name__ == '__main__':
    unittest.main()

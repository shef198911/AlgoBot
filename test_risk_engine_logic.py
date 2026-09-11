import unittest
from risk_manager import StructureRiskEngine
from config import MIN_RR, MIN_SL_ATR

class TestRiskEngineLogic(unittest.TestCase):
    def setUp(self):
        self.rm = StructureRiskEngine()
        self.atr = 100.0
        self.entry = 1000.0

    def run_plan(self, direction, ctx, atr=None):
        if atr is None:
            atr = self.atr
        return self.rm.build_trade_plan(
            direction=direction,
            entry=self.entry,
            setup_type="TEST",
            ctx=ctx,
            atr=atr
        )

    # LONG Tests
    def test_long_rr_0_7_to_fallback(self):
        ctx = {'nearest_support': 900.0, 'nearest_resistance': 1070.0 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 1187.5)

    def test_long_rr_0_97_to_fallback(self):
        ctx = {'nearest_support': 900.0, 'nearest_resistance': 1097.0 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 1187.5)

    def test_long_rr_1_49_to_fallback(self):
        ctx = {'nearest_support': 900.0, 'nearest_resistance': 1149.0 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 1187.5)

    def test_long_rr_1_5_uses_structural(self):
        ctx = {'nearest_support': 900.0, 'nearest_resistance': 1187.5 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 1187.5)

    def test_long_tp1_0_8_tp2_1_8(self):
        ctx = {
            'nearest_support': 900.0, 
            'nearest_resistance': 1080.0 + (self.atr * 0.1),
            'swing_high': 1225.0 + (self.atr * 0.1)
        }
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 1225.0)

    def test_long_sl_too_tight(self):
        ctx = {'nearest_support': 990.0, 'nearest_resistance': 1200.0 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['stop_loss'], 950.0)
        self.assertEqual(res['take_profit'], 1200.0) # Used structural because 1200 > 1075

    def test_long_technical_tp_exceeds_max(self):
        ctx = {'nearest_support': 400.0, 'nearest_resistance': 1100.0 + (self.atr * 0.1)}
        res = self.run_plan("LONG", ctx)
        self.assertFalse(res['valid'])
        self.assertEqual(res['reason'], 'technical_tp_exceeds_max_limit')

    def test_long_bad_geometry(self):
        ctx = {'nearest_support': 1100.0}
        res = self.run_plan("LONG", ctx)
        self.assertFalse(res['valid'])

    # SHORT Tests
    def test_short_rr_0_7_to_fallback(self):
        ctx = {'nearest_resistance': 1100.0, 'nearest_support': 930.0 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 812.5)

    def test_short_rr_0_97_to_fallback(self):
        ctx = {'nearest_resistance': 1100.0, 'nearest_support': 903.0 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 812.5)

    def test_short_rr_1_49_to_fallback(self):
        ctx = {'nearest_resistance': 1100.0, 'nearest_support': 851.0 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 812.5)

    def test_short_rr_1_5_uses_structural(self):
        ctx = {'nearest_resistance': 1100.0, 'nearest_support': 812.5 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 812.5)

    def test_short_tp1_0_8_tp2_1_8(self):
        ctx = {
            'nearest_resistance': 1100.0, 
            'nearest_support': 920.0 - (self.atr * 0.1),
            'swing_low': 775.0 - (self.atr * 0.1)
        }
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['take_profit'], 775.0)

    def test_short_sl_too_tight(self):
        ctx = {'nearest_resistance': 1010.0, 'nearest_support': 800.0 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertTrue(res['valid'])
        self.assertEqual(res['stop_loss'], 1050.0)
        self.assertEqual(res['take_profit'], 800.0)

    def test_short_technical_tp_exceeds_max(self):
        ctx = {'nearest_resistance': 1600.0, 'nearest_support': 900.0 - (self.atr * 0.1)}
        res = self.run_plan("SHORT", ctx)
        self.assertFalse(res['valid'])
        self.assertEqual(res['reason'], 'technical_tp_exceeds_max_limit')

    def test_short_bad_geometry(self):
        ctx = {'nearest_resistance': 900.0}
        res = self.run_plan("SHORT", ctx)
        self.assertFalse(res['valid'])

if __name__ == '__main__':
    unittest.main()

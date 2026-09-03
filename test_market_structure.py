import unittest
import pandas as pd
import numpy as np
from config import FEATURE_COLUMNS, SWING_K
from market_structure import MarketStructureEngine
from strategy_ta import TAStrategy

class TestMarketStructureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)

    def _create_df(self, closes, highs=None, lows=None, opens=None, volumes=None):
        n = len(closes)
        closes = np.array(closes, dtype=float)
        highs = np.array(highs if highs is not None else closes * 1.002, dtype=float)
        lows = np.array(lows if lows is not None else closes * 0.998, dtype=float)
        opens = np.array(opens if opens is not None else closes, dtype=float)
        volumes = np.array(volumes if volumes is not None else np.ones(n) * 1000.0, dtype=float)
        
        timestamps = pd.date_range('2026-01-01', periods=n, freq='15min')
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        return df

    def test_01_breakout_confirmed_with_close(self):
        """1. Обычный breakout: свеча закрывается строго выше зоны сопротивления."""
        # Создаем свинг хай на свече 3: [100, 101, 102, 105, 102, 101, 100] (при k=3)
        prices = [100, 101, 102, 105, 102, 101, 100, 100, 100, 107]
        df = self._create_df(prices)
        res = self.engine.analyze(df)
        # На последней свече (107 > 105) должен быть зафиксирован breakout long
        self.assertEqual(res['IS_BREAKOUT_LONG'].iloc[-1], 1.0)

    def test_02_wick_breakout_rejected(self):
        """2. Прокол тенью (Wick) выше уровня, но закрытие ниже - НЕ считается breakout."""
        # Уровень на 105. На свече 9: high=107, но close=104
        closes = [100, 101, 102, 105, 102, 101, 100, 100, 100, 104]
        highs  = [100.1, 101.1, 102.1, 105.1, 102.1, 101.1, 100.1, 100.1, 100.1, 107.0]
        df = self._create_df(closes, highs=highs)
        res = self.engine.analyze(df)
        self.assertEqual(res['IS_BREAKOUT_LONG'].iloc[-1], 0.0)
        # Это должен быть LIQUIDITY_SWEEP_HIGH!
        self.assertEqual(res['LIQUIDITY_SWEEP_HIGH'].iloc[-1], 1.0)

    def test_03_breakout_and_retest_cycle(self):
        """3. Полный цикл: Breakout ➔ Retest ➔ Confirmation ➔ Entry."""
        # Свинг 105 подтвержден на свече 6.
        # Свеча 7: Пробой (закрытие 108).
        # Свеча 8: Откат к 105.2 с бычьим закрытием.
        closes = [100, 101, 102, 105, 102, 101, 100, 108, 105.5]
        highs  = [100.1, 101.1, 102.1, 105.1, 102.1, 101.1, 100.1, 108.5, 106.0]
        lows   = [99.9, 100.9, 101.9, 104.9, 101.9, 100.9, 99.9, 107.0, 105.0]
        opens  = [100, 101, 102, 105, 102, 101, 100, 102.0, 105.1]
        df = self._create_df(closes, highs=highs, lows=lows, opens=opens)
        res = self.engine.analyze(df)
        self.assertEqual(res['IS_BREAKOUT_LONG'].iloc[7], 1.0)
        self.assertEqual(res['IS_RETEST_LONG'].iloc[8], 1.0)
        self.assertEqual(res['engine_setup'].iloc[8], 'BREAKOUT_RETEST')

    def test_04_breakout_without_retest_no_entry(self):
        """4. Breakout без ретеста: сигнал на вход НЕ дается (ждем ретест)."""
        closes = [100, 101, 102, 105, 102, 101, 100, 108, 109, 110]
        df = self._create_df(closes)
        res = self.engine.analyze(df)
        # На свече 7 был пробой, но на свече 7 нет сигнала на вход, так как ждем ретест
        self.assertEqual(res['IS_BREAKOUT_LONG'].iloc[7], 1.0)
        self.assertEqual(res['engine_setup'].iloc[7], 'None')

    def test_05_retest_timeout_expired(self):
        """5. Таймаут ретеста: если цена не вернулась за RETEST_MAX_BARS, сетап истекает."""
        # k=3, max_bars=3
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=2)
        # Пробой на свече 7, затем 4 свечи цена улетает вверх
        closes = [100, 101, 102, 105, 102, 101, 100, 108, 110, 112, 114, 105.2]
        df = self._create_df(closes)
        res = engine.analyze(df)
        # На последней свече (105.2) ретест не должен сработать, так как сетап уже expired
        self.assertEqual(res['IS_RETEST_LONG'].iloc[-1], 0.0)

    def test_06_retest_invalidated(self):
        """6. Инвалидация сетапа: если цена после пробоя провалилась глубоко ниже уровня."""
        closes = [100, 101, 102, 105, 102, 101, 100, 108, 98.0, 105.2]
        df = self._create_df(closes)
        res = self.engine.analyze(df)
        # После глубокого провала на 98 сетап инвалидирован
        self.assertEqual(res['IS_RETEST_LONG'].iloc[-1], 0.0)

    def test_07_support_bounce(self):
        """7. Support Bounce: касание поддержки с пин-баром откупа."""
        # Свинг лоу на 90. Цена возвращается к 90.2 с длинной нижней тенью.
        closes = [100, 95, 92, 90, 92, 95, 100, 98, 90.3]
        lows   = [99.5, 94.5, 91.5, 89.9, 91.5, 94.5, 99.5, 97.5, 88.5] # Длинная тень снизу на последней свече
        opens  = [100, 95, 92, 90, 92, 95, 100, 98, 90.2]
        highs  = [100.1, 95.1, 92.1, 90.1, 92.1, 95.1, 100.1, 98.1, 90.4]
        df = self._create_df(closes, highs=highs, lows=lows, opens=opens)
        res = self.engine.analyze(df)
        self.assertEqual(res['BULLISH_REJECTION'].iloc[-1], 1.0)
        self.assertIn(res['engine_setup'].iloc[-1], ['SUPPORT_BOUNCE', 'LIQUIDITY_SWEEP_LONG'])

    def test_08_market_structure_hh_hl_and_bos(self):
        """8. Структура рынка (HH/HL) и Break of Structure (BOS)."""
        # Сформируем два восходящих свинга
        closes = [100, 105, 102, 100, 104, 108, 105, 103, 106, 112]
        highs  = [100, 106, 102, 100, 104, 109, 105, 103, 106, 113]
        lows   = [99,  104, 101, 99,  103, 107, 104, 102, 105, 111]
        df = self._create_df(closes, highs=highs, lows=lows)
        res = self.engine.analyze(df)
        self.assertIn('BOS_LONG', res.columns)
        self.assertIn('CHOCH_LONG', res.columns)

    def test_09_duplicate_setup_prevention(self):
        """9. Защита от повторного входа: один сетап дает ровно один сигнал."""
        closes = [100, 101, 102, 105, 102, 101, 100, 108, 105.5, 105.6]
        highs  = [100.1, 101.1, 102.1, 105.1, 102.1, 101.1, 100.1, 108.5, 106.0, 106.0]
        lows   = [99.9, 100.9, 101.9, 104.9, 101.9, 100.9, 99.9, 107.0, 105.0, 105.0]
        opens  = [100, 101, 102, 105, 102, 101, 100, 102.0, 105.1, 105.2]
        df = self._create_df(closes, highs=highs, lows=lows, opens=opens)
        res = self.engine.analyze(df)
        # На свече 8 сетап сработал. На свече 9 тот же самый сетап НЕ должен сработать повторно!
        self.assertEqual(res['IS_RETEST_LONG'].iloc[8], 1.0)
        self.assertEqual(res['IS_RETEST_LONG'].iloc[9], 0.0)

    def test_10_strict_zero_lookahead_bias(self):
        """10. КРИТИЧЕСКАЯ ПРОВЕРКА: Нулевой Lookahead Bias."""
        # Генерируем 100 случайных свечей
        np.random.seed(123)
        n = 100
        returns = np.random.normal(0.0001, 0.005, n)
        c = 100.0 * np.cumprod(1 + returns)
        df_full = self._create_df(c)

        # Анализируем первые 60 свечей
        df_60 = df_full.iloc[:60].copy()
        res_60 = self.engine.analyze(df_60)

        # Анализируем все 100 свечей
        res_100 = self.engine.analyze(df_full.copy())

        # Значения на 59-й свече (индекс 59) в res_60 и res_100 ДОЛЖНЫ БЫТЬ АБСОЛЮТНО ИДЕНТИЧНЫ!
        for col in ['DIST_SUP_PCT', 'DIST_RES_PCT', 'MARKET_STRUCTURE', 'IS_BREAKOUT_LONG', 'IS_RETEST_LONG', 'engine_signal', 'SETUP_SCORE']:
            val_60 = res_60[col].iloc[59]
            val_100 = res_100[col].iloc[59]
            self.assertEqual(val_60, val_100, f"LOOKAHEAD BIAS DETECTED in column {col}! {val_60} != {val_100}")

    def test_12_resistance_rejection(self):
        """12. Resistance Rejection: цена у сопротивления с пин-баром продаж."""
        # Свинг хай на 110. Цена возвращается к 109.8 с длинной верхней тенью.
        closes = [100, 105, 108, 110, 108, 105, 100, 102, 109.8]
        highs  = [100.1, 105.1, 108.1, 110.1, 108.1, 105.1, 100.1, 102.1, 112.5] # Длинная тень сверху
        opens  = [100, 105, 108, 110, 108, 105, 100, 102, 109.7]
        lows   = [99.9, 104.9, 107.9, 109.9, 107.9, 104.9, 99.9, 101.9, 109.5]
        df = self._create_df(closes, highs=highs, lows=lows, opens=opens)
        res = self.engine.analyze(df)
        self.assertEqual(res['BEARISH_REJECTION'].iloc[-1], 1.0)
        self.assertIn(res['engine_setup'].iloc[-1], ['RESISTANCE_REJECTION', 'LIQUIDITY_SWEEP_SHORT'])

    def test_13_breakdown_retest_short(self):
        """13. Полный цикл Breakdown ➔ Retest ➔ Entry для SHORT."""
        # Свинг лоу 95 подтвержден на свече 6.
        # Свеча 7: Пробой вниз (закрытие 92).
        # Свеча 8: Откат к 94.8 снизу с медвежьим закрытием.
        closes = [100, 98, 96, 95, 96, 98, 100, 92.0, 94.5]
        highs  = [100.1, 98.1, 96.1, 95.1, 96.1, 98.1, 100.1, 93.0, 95.0]
        lows   = [99.9, 97.9, 95.9, 94.9, 95.9, 97.9, 99.9, 91.5, 94.0]
        opens  = [100, 98, 96, 95, 96, 98, 100, 98.0, 94.8]
        df = self._create_df(closes, highs=highs, lows=lows, opens=opens)
        res = self.engine.analyze(df)
        self.assertEqual(res['IS_BREAKOUT_SHORT'].iloc[7], 1.0)
        self.assertEqual(res['IS_RETEST_SHORT'].iloc[8], 1.0)
        self.assertEqual(res['engine_setup'].iloc[8], 'BREAKDOWN_RETEST')

    def test_14_liquidity_sweep_low(self):
        """14. Liquidity Sweep Low: прокол поддержки тенью, закрытие внутри."""
        closes = [100, 95, 92, 90, 92, 95, 100, 98, 91.0]
        lows   = [99.5, 94.5, 91.5, 89.9, 91.5, 94.5, 99.5, 97.5, 87.0] # Прокол ниже 89.9
        df = self._create_df(closes, lows=lows)
        res = self.engine.analyze(df)
        self.assertEqual(res['LIQUIDITY_SWEEP_LOW'].iloc[-1], 1.0)

    def test_15_bearish_bos_and_choch(self):
        """15. Bearish BOS и Bearish CHOCH."""
        closes = [100, 95, 98, 93, 96, 91, 94, 88]
        df = self._create_df(closes)
        res = self.engine.analyze(df)
        self.assertIn('BOS_SHORT', res.columns)
        self.assertIn('CHOCH_SHORT', res.columns)

    def test_11_all_feature_columns_populated(self):
        """11. Проверка наличия всех признаков FEATURE_COLUMNS без NaN и Inf."""
        np.random.seed(42)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.004, 150))
        df = self._create_df(c)
        ta = TAStrategy()
        analyzed = ta.generate_features_and_signals(df)
        self.assertIsNotNone(analyzed)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, analyzed.columns, f"Колонка {col} отсутствует в TA DataFrame!")
            self.assertEqual(analyzed[col].isna().sum(), 0, f"NaN в колонке {col}!")
            self.assertFalse(np.isinf(analyzed[col]).any(), f"Inf в колонке {col}!")

if __name__ == '__main__':
    unittest.main()

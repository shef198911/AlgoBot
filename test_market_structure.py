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

    def test_08_bullish_bos_and_choch(self):
        """8. BOS LONG and CHOCH LONG (Single Candle Events)."""
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
                self.assertEqual(res['CHOCH_LONG'].iloc[idx + 1], 0.0)

    def test_09_duplicate_setup_prevention(self):
        """9. ONE SETUP = ONE ENTRY (Lifecycle check)"""
        closes = [
            100, 100,
            100, 105, 110, 105, 100,
            100, 100, 100,
            115, 116,
            111.0, 110.1, 115,
            112.0, 110.1, 115
        ]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=15)
        res = engine.analyze(df)
        retest_count = sum(res['engine_setup'] == 'BREAKOUT_RETEST')
        self.assertEqual(retest_count, 1, "Multiple BREAKOUT_RETEST setups triggered for one setup!")

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
        """15. BOS SHORT and CHOCH SHORT (Single Candle Events)."""
        closes = [
            100, 100,
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
                self.assertEqual(res['CHOCH_SHORT'].iloc[idx + 1], 0.0)

    def test_16_bos_is_single_candle_event(self):
        """16. P0. 2: BOS - строго точечное событие на 1 свечу (не держится несколько свечей)."""
        closes = [100, 102, 105, 102, 100, 98, 95, 98, 100, 105, 110, 105, 100, 98, 96, 98, 100, 105, 112, 113, 114]
        df = self._create_df(closes)
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        res = engine.analyze(df)
        
        self.assertEqual(res['BOS_LONG'].iloc[18], 1.0, "BOS_LONG must trigger exactly at index 18")
        self.assertEqual(res['BOS_LONG'].iloc[19], 0.0, "BOS_LONG must reset to 0 at index 19")

    def test_17_setup_score_real_calculation(self):
        """17. P0. 1: Setup Score считается реально без фиктивных True."""
        score = self.engine.calculate_setup_score(
            direction='LONG',
            has_breakout=True,
            has_retest=True,
            has_rejection=True,
            vol_ratio=1.5,
            structure_aligned=True,
            ema_fast=105.0,
            ema_slow=100.0,
            close=106.0,
            vwap=104.0,
            rsi=55.0,
            price_roc=0.02,
            adx=30.0,
            log_diagnostics=True
        )
        # Все условия идеальные -> балл должен быть максимальным 100
        self.assertEqual(score, 100.0)

        # Теперь ухудшаем тренд и моментум
        score_bad = self.engine.calculate_setup_score(
            direction='LONG',
            has_breakout=False,
            has_retest=False,
            has_rejection=False,
            vol_ratio=0.8,
            structure_aligned=False,
            ema_fast=90.0,
            ema_slow=100.0,
            close=89.0,
            vwap=95.0,
            rsi=75.0,
            price_roc=-0.05,
            adx=15.0
        )
        self.assertEqual(score_bad, 0.0)

    def test_18_range_detection_and_bounce(self):
        """18. P1. 6: Настоящий Range Detection и Range Bounce."""
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Коридор около 100-104 с несколькими свингами (k=2)
        prices = [100, 102, 104, 102, 100, 102, 104, 102, 100, 102, 104, 102, 100, 100.1]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        lows[-1] = 98.5  # Откуп на нижней границе
        df = self._create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        self.assertIn('RANGE_BOUNCE', res['engine_setup'].values)

    def test_19_sr_strength_calculation(self):
        """19. P1. 7: Расчет реальной силы уровней SR_STRENGTH."""
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        prices = [100, 102, 104, 102, 100, 102, 104, 102, 100, 102, 104, 102, 100, 100.1]
        df = self._create_df(prices)
        res = engine.analyze(df)
        # Сила уровня при повторных касаниях должна быть больше базовой 25
        self.assertTrue((res['SR_STRENGTH'] > 25.0).any())

    def test_20_trend_pullback(self):
        """20. P1. 5: Настоящий Trend Pullback в направлении подтвержденной структуры."""
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Бычья структура: 2 восходящих свинга, затем откат к зоне отката
        prices = [100, 103, 106, 103, 101, 105, 110, 107, 104, 107, 115, 111, 106, 106.5]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        opens = [p for p in prices]
        lows[-1] = 104.0  # Бычий пин-бар на откате
        df = self._create_df(prices, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        self.assertIn('TREND_PULLBACK', res['engine_setup'].values)

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


    def test_21_no_lookahead_swing_k(self):
        """21. NO LOOKAHEAD SWING_K"""
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)
        closes = [100, 101, 102, 103, 104, 110, 104, 103, 102, 101, 100]
        df = self._create_df(closes)
        df.loc[5, 'high'] = 110.0
        res = engine.analyze(df)
        val_5 = res['NEAREST_RESISTANCE'].iloc[5]
        val_6 = res['NEAREST_RESISTANCE'].iloc[6]
        val_7 = res['NEAREST_RESISTANCE'].iloc[7]
        val_8 = res['NEAREST_RESISTANCE'].iloc[8]
        self.assertTrue(val_8 != val_7, "Swing must be confirmed exactly at t+3")
        self.assertTrue(val_8 < 111.0 and val_8 > 108.0)

    def test_22_multiple_active_setups(self):
        """22. MULTIPLE ACTIVE SETUPS"""
        closes = [
            100, 100,
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
        self.assertTrue(len(retests) >= 2, "Did not get 2 retests! Setup A might have been deleted.")




    def test_23_train_live_parity(self):
        """23. TRAIN / LIVE PARITY"""
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
        """24. ML FEATURE ORDER"""
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


    def test_23_train_live_parity(self):
        """23. TRAIN / LIVE PARITY"""
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
        """24. ML FEATURE ORDER"""
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
        mixed_features = pd.Series({k: 0.0 for k in reversed(FEATURE_COLUMNS)})
        ml.evaluate_signal(mixed_features)
        infer_columns = list(ml.ensemble.last_X.columns)
        self.assertEqual(infer_columns, FEATURE_COLUMNS)

if __name__ == '__main__':
    unittest.main()
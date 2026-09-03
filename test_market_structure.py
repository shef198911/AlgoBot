import unittest
import pandas as pd
import numpy as np
from config import FEATURE_COLUMNS, TRADING_MODE
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from market_structure import enrich_with_market_structure, calculate_candle_patterns, calculate_market_structure

class TestMarketStructureAndTA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Генерируем 200 свечей реалистичных синтетических данных для быстрого и надежного теста
        np.random.seed(42)
        n = 300
        timestamps = pd.date_range('2026-01-01', periods=n, freq='15min')
        
        # Симулируем случайное блуждание цены
        returns = np.random.normal(0.0002, 0.005, n)
        close = 100.0 * np.cumprod(1 + returns)
        high = close * (1 + np.abs(np.random.normal(0, 0.004, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.004, n)))
        open_p = (close + low + high) / 3.0
        volume = np.random.uniform(500, 5000, n)

        cls.df = pd.DataFrame({
            'timestamp': timestamps,
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    def test_candle_patterns(self):
        pats = calculate_candle_patterns(self.df)
        self.assertIn('WICK_UPPER_RATIO', pats.columns)
        self.assertIn('WICK_LOWER_RATIO', pats.columns)
        self.assertIn('BULLISH_REJECTION', pats.columns)
        self.assertIn('BEARISH_REJECTION', pats.columns)
        self.assertTrue((pats['WICK_UPPER_RATIO'] >= 0).all())
        self.assertTrue((pats['WICK_LOWER_RATIO'] >= 0).all())
        self.assertEqual(pats['BULLISH_REJECTION'].isna().sum(), 0)

    def test_market_structure(self):
        struct = calculate_market_structure(self.df, swing_k=3)
        self.assertIn('NEAREST_SUPPORT', struct.columns)
        self.assertIn('NEAREST_RESISTANCE', struct.columns)
        self.assertIn('DIST_SUP_PCT', struct.columns)
        self.assertIn('DIST_RES_PCT', struct.columns)
        self.assertIn('MARKET_STRUCTURE', struct.columns)
        self.assertIn('IS_BREAKOUT_LONG', struct.columns)
        self.assertIn('IS_RETEST_LONG', struct.columns)
        
        # Дистанции должны быть неотрицательными
        self.assertTrue((struct['DIST_SUP_PCT'] >= 0).all())
        self.assertTrue((struct['DIST_RES_PCT'] >= 0).all())
        self.assertEqual(struct['DIST_SUP_PCT'].isna().sum(), 0)

    def test_ta_strategy_features_and_signals(self):
        ta = TAStrategy()
        analyzed = ta.generate_features_and_signals(self.df)
        self.assertIsNotNone(analyzed)
        self.assertFalse(analyzed.empty)
        
        # Проверяем, что ВСЕ признаки из config.FEATURE_COLUMNS присутствуют!
        for col in FEATURE_COLUMNS:
            self.assertIn(col, analyzed.columns, f"Признак {col} отсутствует в TA DataFrame!")
            self.assertEqual(analyzed[col].isna().sum(), 0, f"Признак {col} содержит NaN!")
            self.assertFalse(np.isinf(analyzed[col]).any(), f"Признак {col} содержит Inf!")
            
        # Проверяем сигналы и сетапы
        self.assertIn('ta_signal', analyzed.columns)
        self.assertIn('ta_setup', analyzed.columns)
        unique_signals = set(analyzed['ta_signal'].unique())
        self.assertTrue(unique_signals.issubset({-1, 0, 1}))
        print(f"Тест пройден: {len(analyzed)} свечей обработано успешно, сетапы: {analyzed['ta_setup'].value_counts().to_dict()}")

if __name__ == '__main__':
    unittest.main()

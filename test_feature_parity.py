import unittest
import pandas as pd
from strategy_ta import TAStrategy
from config import FEATURE_COLUMNS

class TestFeatureParity(unittest.TestCase):
    def setUp(self):
        self.ta_bot = TAStrategy()
        
    def test_features_generated_match_feature_columns(self):
        # Create dummy df
        data = {
            'timestamp': pd.date_range('2023-01-01', periods=100, freq='1h'),
            'open': [50000.0] * 100,
            'high': [51000.0] * 100,
            'low': [49000.0] * 100,
            'close': [50500.0] * 100,
            'volume': [10.0] * 100,
        }
        df = pd.DataFrame(data)
        
        df_analyzed = self.ta_bot.generate_features_and_signals(df)
        
        self.assertIsNotNone(df_analyzed)
        
        missing_features = []
        for feature in FEATURE_COLUMNS:
            if feature not in df_analyzed.columns:
                missing_features.append(feature)
                
        self.assertEqual(len(missing_features), 0, f"Missing features: {missing_features}")
        self.assertIn('engine_context', df_analyzed.columns)

if __name__ == '__main__':
    unittest.main()

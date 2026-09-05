import unittest
from unittest.mock import MagicMock, patch
from executor import TraderExecutor

class TestTraderExecutorRecovery(unittest.TestCase):
    def setUp(self):
        self.exchange_mock = MagicMock()
        self.exchange_mock.markets = {'BTC/USDT': {}}
        self.exchange_mock.amount_to_precision.return_value = '0.1'
        self.exchange_mock.price_to_precision.return_value = '50000.0'
        
        self.executor = TraderExecutor(self.exchange_mock)
        # Mock risk engine to bypass it for simpler tests
        self.executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True,
            'risk_distance': 100,
            'stop_loss': 49000,
            'take_profit': 52000
        })

    @patch('executor.logger')
    def test_execute_trade_success(self, mock_logger):
        # Setup mock returns
        self.exchange_mock.fetch_positions.return_value = []
        self.exchange_mock.create_market_order.return_value = {
            'id': 'market123',
            'average': 50000.0,
            'filled': 1.0
        }
        self.exchange_mock.create_order.side_effect = [
            {'id': 'sl123'}, # SL
            {'id': 'tp123'}  # TP
        ]
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertTrue(success)
        self.assertIn('BTC/USDT', self.executor.positions)
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'sl123')
        self.assertEqual(self.executor.positions['BTC/USDT']['tp_order_id'], 'tp123')

    @patch('executor.logger')
    def test_execute_trade_sl_fail_triggers_emergency_close(self, mock_logger):
        # Setup mock returns
        self.exchange_mock.fetch_positions.side_effect = [
            [], # First call in check_position_status
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.1'}}] # Second call in emergency_close
        ]
        self.exchange_mock.create_market_order.return_value = {
            'id': 'market123',
            'average': 50000.0,
            'filled': 1.0
        }
        # First create_order (SL) fails
        self.exchange_mock.create_order.side_effect = Exception("API SL Error")
        
        # Emergency close should fetch position
        # Already handled by side_effect above
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        # Verify emergency close was called
        self.exchange_mock.create_market_order.assert_any_call('BTC/USDT', 'sell', 0.1, params={'reduceOnly': True})

if __name__ == '__main__':
    unittest.main()

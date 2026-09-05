import unittest
from unittest.mock import MagicMock, patch
from executor import TraderExecutor
from config import MAX_CAPITAL_USDT

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
        self.exchange_mock.fetch_positions.return_value = []
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.1}
        self.exchange_mock.create_order.side_effect = [{'id': 'sl123'}, {'id': 'tp123'}]
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertTrue(success)
        self.assertIn('BTC/USDT', self.executor.positions)
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'sl123')
        self.assertEqual(self.executor.positions['BTC/USDT']['tp_order_id'], 'tp123')

    @patch('executor.logger')
    def test_execute_trade_sl_fail_triggers_emergency_close(self, mock_logger):
        self.exchange_mock.fetch_positions.side_effect = [
            [], # check_position_status
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.1'}}] # emergency_close
        ]
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.1}
        self.exchange_mock.create_order.side_effect = Exception("API SL Error")
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.exchange_mock.create_market_order.assert_any_call('BTC/USDT', 'sell', 0.1, params={'reduceOnly': True})

    @patch('executor.logger')
    def test_execute_trade_tp_fail_does_not_close(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = []
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.1}
        
        def create_order_mock(symbol, type, side, amount, price=None, params={}):
            if type == 'STOP_MARKET': return {'id': 'sl123'}
            raise Exception("API TP Error")
            
        self.exchange_mock.create_order.side_effect = create_order_mock
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertTrue(success)
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'sl123')
        self.assertIsNone(self.executor.positions['BTC/USDT']['tp_order_id'])

    @patch('executor.logger')
    def test_max_capital_limit(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = []
        # Pre-fill capital
        self.executor.positions['ETH/USDT'] = {'margin_required': MAX_CAPITAL_USDT - 1}
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.assertIn("Лимит капитала исчерпан", self.executor.last_error)
        self.assertNotIn('BTC/USDT', self.executor.positions)
        
    @patch('executor.logger')
    def test_unknown_amount_fallback_removed(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = []
        # Simulate MARKET order without 'filled' field and fetch_positions returning empty
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0}
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.assertEqual(self.executor.last_error, "UNKNOWN_AMOUNT")
        self.assertNotIn('BTC/USDT', self.executor.positions)

    @patch('executor.logger')
    def test_check_position_status_verifies_open_orders(self, mock_logger):
        self.executor.positions['BTC/USDT'] = {
            'side': 'long', 'entry': 50000.0, 'max_price': 50000.0, 'min_price': 50000.0,
            'sl_order_id': 'old_sl', 'tp_order_id': 'old_tp', 'amount': 0.1, 'sl_price': 49000.0
        }
        self.exchange_mock.fetch_positions.return_value = [{'symbol': 'BTC/USDT', 'side': 'long', 'entryPrice': 50000.0, 'info': {'positionAmt': '0.1'}}]
        
        # Open orders on exchange returns NOTHING (no SL/TP)
        self.exchange_mock.fetch_open_orders.return_value = []
        
        # When check_position_status runs, it should discover SL is missing and recreate it
        self.exchange_mock.create_order.return_value = {'id': 'new_sl'}
        
        res = self.executor.check_position_status('BTC/USDT')
        
        self.assertTrue(res) # Still active
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'new_sl')
        
    @patch('executor.logger')
    def test_pending_margins_released_on_fail(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = []
        # Force market order to fail
        self.exchange_mock.create_market_order.side_effect = Exception("API Market Error")
        
        self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        # After failure, pending_margins must be clear
        self.assertNotIn('BTC/USDT', self.executor.pending_margins)

if __name__ == '__main__':
    unittest.main()

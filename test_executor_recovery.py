import unittest
from unittest.mock import MagicMock, patch

from executor import TraderExecutor
from config import MAX_CAPITAL_USDT

class TestTraderExecutorRecovery(unittest.TestCase):
    def setUp(self):
        self.exchange_mock = MagicMock()
        self.exchange_mock.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        self.exchange_mock.markets = {'BTC/USDT': {}}
        import math
        self.exchange_mock.amount_to_precision.side_effect = lambda sym, amt: f"{math.floor(float(amt)*10000)/10000.0}"
        self.exchange_mock.price_to_precision.side_effect = lambda sym, p: f"{float(p):.2f}"
        self.mock_cap_exists = patch('capital_manager.os.path.exists', return_value=False).start()
        self.addCleanup(patch.stopall)
        
        import config
        config.MAX_RISK_PER_TRADE_PCT = 100.0
        
        self.executor = TraderExecutor(self.exchange_mock, working_capital=500.0)
        self.executor.update_real_balance(10000.0)
        # Mock risk engine to bypass it for simpler tests
        self.executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True,
            'risk_distance': 100,
            'stop_loss': 49000,
            'take_profit': 52000
        })
        
    def tearDown(self):
        import os
        for f in ['live_state.json', 'bot_equity.json']:
            if os.path.exists(f):
                os.remove(f)

    @patch('executor.logger')
    def test_execute_trade_success(self, mock_logger):
        pos_empty = [
            {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
            {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
        ]
        pos_filled = [
            {'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.01', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
        ]
        self.exchange_mock.fetch_positions.side_effect = [pos_empty, pos_empty, pos_filled]
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.01}
        self.exchange_mock.create_order.side_effect = [{'id': 'sl123'}, {'id': 'tp123'}]
        self.exchange_mock.price_to_precision.side_effect = lambda sym, p: f"{float(p):.2f}"
        self.exchange_mock.fetch_open_orders.return_value = [
            {'id': 'sl123', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 49000.0, 'amount': 0.01, 'status': 'open'}
        ]
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertTrue(success)
        self.assertIn('BTC/USDT', self.executor.positions)
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'sl123')
        self.assertEqual(self.executor.positions['BTC/USDT']['tp_order_id'], 'tp123')

    @patch('executor.logger')
    def test_execute_trade_sl_fail_triggers_emergency_close(self, mock_logger):
        self.exchange_mock.fetch_positions.side_effect = [
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.1},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
],
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.1},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
],
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.01', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0}]
        ]
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.01}
        self.exchange_mock.create_order.side_effect = Exception("API SL Error")
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.exchange_mock.create_market_order.assert_any_call('BTC/USDT', 'sell', 0.01, params={'reduceOnly': True})

    @patch('executor.logger')
    def test_execute_trade_tp_fail_does_not_close(self, mock_logger):
        pos_empty = [
            {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
            {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
        ]
        pos_filled = [
            {'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.01', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
        ]
        self.exchange_mock.fetch_positions.side_effect = [pos_empty, pos_empty, pos_filled]
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0, 'filled': 0.01}
        self.exchange_mock.price_to_precision.side_effect = lambda sym, p: f"{float(p):.2f}"
        
        def create_order_mock(symbol, type, side, amount, price=None, params={}):
            if type == 'STOP_MARKET': return {'id': 'sl123'}
            raise Exception("API TP Error")
            
        self.exchange_mock.create_order.side_effect = create_order_mock
        self.exchange_mock.fetch_open_orders.return_value = [
            {'id': 'sl123', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 49000.0, 'amount': 0.01, 'status': 'open'}
        ]
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertTrue(success)
        self.assertEqual(self.executor.positions['BTC/USDT']['sl_order_id'], 'sl123')
        self.assertIsNone(self.executor.positions['BTC/USDT']['tp_order_id'])

    @patch('executor.logger')
    def test_max_capital_limit(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        # Pre-fill capital
        self.executor.positions['ETH/USDT'] = {'margin_required': MAX_CAPITAL_USDT - 1}
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.assertIn("недостаточно", self.executor.last_error)
        self.assertNotIn('BTC/USDT', self.executor.positions)
        
    @patch('executor.logger')
    def test_unknown_amount_fallback_removed(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        # Simulate MARKET order without 'filled' field and fetch_positions returning empty
        self.exchange_mock.create_market_order.return_value = {'id': 'market123', 'average': 50000.0}
        
        success = self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        self.assertFalse(success)
        self.assertEqual(self.executor.last_error, "UNKNOWN_AMOUNT")
        
        # Since emergency_close failed to find the position on exchange, it leaves the state intact for recovery
        self.assertIn('BTC/USDT', self.executor.positions)
        self.assertIsNone(self.executor.positions['BTC/USDT']['amount'])
        self.assertEqual(self.executor.positions['BTC/USDT'].get('status'), 'UNKNOWN')


        
    @patch('executor.logger')
    def test_pending_margins_released_on_fail(self, mock_logger):
        self.exchange_mock.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        # Force market order to fail
        self.exchange_mock.create_market_order.side_effect = Exception("API Market Error")
        
        self.executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, 100.0, 0.05, 'BULL_FLAG', {'swing_low': 49000})
        
        # After failure, pending_margins must be clear
        self.assertNotIn('BTC/USDT', self.executor.pending_margins)

if __name__ == '__main__':
    unittest.main()

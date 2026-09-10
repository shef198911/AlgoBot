import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from unittest.mock import MagicMock, patch

# Prevent real telegram messages during tests
patch('telegram_notifier.TelegramNotifier.send_message').start()

from executor import TraderExecutor
import config

class TestExecutor(unittest.TestCase):
    def setUp(self):
        # Disable logging to avoid console spam
        self.mock_logger = MagicMock()
        
        # Configure mock exchange
        self.mock_exchange = MagicMock()
        self.mock_exchange.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        self.mock_exchange.markets = {'TEST/USDT': {}}
        self.mock_exchange.price_to_precision.side_effect = lambda sym, price: f"{price:.4f}"
        import math
        self.mock_exchange.amount_to_precision.side_effect = lambda sym, amt: f"{math.floor(float(amt)*10000)/10000.0}"
        self.mock_cap_exists = patch('capital_manager.os.path.exists', return_value=False).start()
        self.addCleanup(patch.stopall)
        
        self.executor = TraderExecutor(self.mock_exchange, working_capital=500.0)
        self.executor.update_real_balance(10000.0)
        self.executor.logger = self.mock_logger
        self.executor.risk_engine = MagicMock()
        
        # Override config dependencies
        config.MAX_CAPITAL_USDT = 1000.0
        config.LEVERAGE = 10
        config.STRUCTURE_RISK_ENABLED = True
        config.MAX_RISK_PERCENT = 10.0
        config.MAX_RISK_PER_TRADE_PCT = 1.0
        
        import capital_manager
        capital_manager.MIN_RISK_USDT = 0.0

    def tearDown(self):
        import os
        for f in ['live_state.json', 'bot_equity.json']:
            if os.path.exists(f):
                os.remove(f)

    @patch('executor.json')
    @patch('executor.open')
    def test_01_execute_trade_success(self, mock_open, mock_json):
        # Mocks
        self.mock_exchange.create_market_order.return_value = {
            'id': 'market_id_123',
            'average': 101.0,
            'filled': 1.0
        }
        
        # Stop loss and take profit orders
        self.mock_exchange.create_order.side_effect = [
            {'id': 'sl_123'},
            {'id': 'tp_123'}
        ]
        
        self.mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_123',
                'symbol': 'TEST/USDT',
                'type': 'stop_market',
                'reduceOnly': True,
                'stopPrice': 100.0,
                'amount': 10.0,
                'status': 'open'
            }
        ]
        
        self.executor.risk_engine.build_trade_plan.return_value = {
            'valid': True,
            'stop_loss': 100.0,
            'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0
        }
        
        engine_context = {'nearest_support': 100.5}
        
        result = self.executor.execute_trade(
            symbol='TEST/USDT',
            side='buy',
            risk_usdt=10.0,
            current_price=101.5, # slightly off fill price
            atr_value=1.0,
            setup_type='SUPPORT_BOUNCE',
            engine_context=engine_context
        )
        
        self.assertTrue(result, self.executor.last_error)
        self.assertIn('TEST/USDT', self.executor.positions)
        
        pos = self.executor.positions['TEST/USDT']
        self.assertEqual(pos['entry'], 101.0) # Check actual fill price
        self.assertEqual(pos['amount'], 1.0) # Check actual filled amount
        self.assertEqual(pos['sl_order_id'], 'sl_123')
        self.assertEqual(pos['tp_order_id'], 'tp_123')

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_02_sl_failure_triggers_emergency_close(self, mock_sleep, mock_open, mock_json):
        # 4. SL first attempt fails, second attempt fails, emergency close triggered
        
        self.mock_exchange.create_market_order.side_effect = [
            # First call: Market Entry
            {
                'id': 'market_id_123',
                'average': 100.0,
                'filled': 5.5
            },
            # Second call: Emergency Close
            {'id': 'emergency_close_123'}
        ]
        
        # Force SL to fail both times
        self.mock_exchange.create_order.side_effect = Exception("Exchange offline")
        
        self.executor.risk_engine.build_trade_plan.return_value = {
            'valid': True,
            'stop_loss': 99.0,
            'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0
        }
        
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        
        self.assertFalse(result)
        # Should NOT be in positions
        self.assertNotIn('TEST/USDT', self.executor.positions)
        
        # Ensure emergency close used the actual amount
        calls = self.mock_exchange.create_market_order.call_args_list
        self.assertEqual(len(calls), 2, calls)
        close_call = calls[1]
        self.assertEqual(close_call[0][0], 'TEST/USDT') # Symbol
        self.assertEqual(close_call[0][1], 'sell') # Close side
        self.assertEqual(close_call[0][2], 5.5) # Actual filled amount!

    @patch('executor.json')
    @patch('executor.open')
    def test_03_tp_failure_retains_position(self, mock_open, mock_json):
        # 5. TP fails -> Position stays open with protective SL
        
        self.mock_exchange.create_market_order.return_value = {
            'id': 'market_id_123',
            'average': 100.0,
            'filled': 1.0
        }
        
        # SL success, TP failure
        def create_order_side_effect(sym, order_type, side, amt, params=None):
            if order_type == 'market':
                return {'id': 'market_id_123', 'average': 100.0, 'filled': 1.0}
            if order_type == 'TAKE_PROFIT_MARKET':
                raise Exception("Network issue during TP")
            if order_type == 'STOP_MARKET':
                return {'id': 'sl_123'}
                
        self.mock_exchange.create_order.side_effect = create_order_side_effect
        
        self.mock_exchange.fetch_open_orders.return_value = [
            {
                'id': 'sl_123',
                'symbol': 'TEST/USDT',
                'type': 'stop_market',
                'reduceOnly': True,
                'stopPrice': 99.0,
                'amount': 10.0,
                'status': 'open'
            }
        ]
        
        self.executor.risk_engine.build_trade_plan.return_value = {
            'valid': True,
            'stop_loss': 99.0,
            'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0
        }
        
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        
        # Still considered a success because SL protects the position
        self.assertTrue(result, self.executor.last_error)
        self.assertIn('TEST/USDT', self.executor.positions)
        
        pos = self.executor.positions['TEST/USDT']
        self.assertEqual(pos['sl_order_id'], 'sl_123')
        self.assertIsNone(pos['tp_order_id'])
        self.assertEqual(pos['amount'], 1.0)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_04_unknown_liquidation_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [
            {'id': 'market_id_123', 'average': 100.0, 'filled': 10.0},
            {'id': 'emergency_close_123'}
        ]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'sl_123', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 99.0, 'amount': 10.0, 'status': 'open'}]
        # Set liquidation to None explicitly
        self.mock_exchange.fetch_positions.return_value = [
            {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 100.0, 'liquidationPrice': None, 'markPrice': 100.0}
        ]
        self.executor.risk_engine.build_trade_plan.return_value = {
            'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0
        }
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)
        self.assertNotIn('TEST/USDT', self.executor.positions)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_05_unknown_liquidation_and_emergency_close_failure(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [
            {'id': 'market_id_123', 'average': 100.0, 'filled': 10.0},
            Exception("Emergency close failed")
        ]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'sl_123', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 99.0, 'amount': 10.0, 'status': 'open'}]
        self.mock_exchange.fetch_positions.return_value = [
            {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 100.0, 'liquidationPrice': None, 'markPrice': 100.0}
        ]
        self.executor.risk_engine.build_trade_plan.return_value = {
            'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0
        }
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)
        self.assertIn('TEST/USDT', self.executor.positions)
        self.assertEqual(self.executor.positions['TEST/USDT']['status'], 'UNKNOWN')

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_06_missing_fetch_open_orders_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [{'id': 'm1', 'average': 100.0, 'filled': 10.0}, {'id': 'ec'}]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.side_effect = Exception("API Error")
        self.executor.risk_engine.build_trade_plan.return_value = {'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0}
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_07_missing_sl_in_returned_orders_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [{'id': 'm1', 'average': 100.0, 'filled': 10.0}, {'id': 'ec'}]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        # sl_123 missing from returned open orders
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'other_id', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 99.0, 'amount': 10.0, 'status': 'open'}]
        self.executor.risk_engine.build_trade_plan.return_value = {'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0}
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_08_incorrect_reduceOnly_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [{'id': 'm1', 'average': 100.0, 'filled': 10.0}, {'id': 'ec'}]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'sl_123', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': False, 'stopPrice': 99.0, 'amount': 10.0, 'status': 'open'}]
        self.executor.risk_engine.build_trade_plan.return_value = {'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0}
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_09_incorrect_stopPrice_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [{'id': 'm1', 'average': 100.0, 'filled': 10.0}, {'id': 'ec'}]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'sl_123', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 95.0, 'amount': 10.0, 'status': 'open'}]
        self.executor.risk_engine.build_trade_plan.return_value = {'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0}
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)

    @patch('executor.json')
    @patch('executor.open')
    @patch('time.sleep', return_value=None)
    def test_10_insufficient_quantity_emergency_close(self, mock_sleep, mock_open, mock_json):
        self.mock_exchange.create_market_order.side_effect = [{'id': 'm1', 'average': 100.0, 'filled': 10.0}, {'id': 'ec'}]
        self.mock_exchange.create_order.return_value = {'id': 'sl_123'}
        self.mock_exchange.fetch_open_orders.return_value = [{'id': 'sl_123', 'symbol': 'TEST/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 99.0, 'amount': 5.0, 'status': 'open'}]
        self.executor.risk_engine.build_trade_plan.return_value = {'valid': True, 'stop_loss': 99.0, 'take_profit': 105.0, 'risk_distance': 1.0, 'risk_usdt': 10.0}
        result = self.executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.5)
        self.assertFalse(result)

    @patch('executor.json')
    @patch('executor.open')
    def test_11_reconciliation_exact_once(self, mock_open, mock_json):
        # We need to simulate restart and EXACT ONCE reconciliation
        # Add a mock position that doesn't have an SL
        self.executor.positions = {'TEST/USDT': {'amount': 10.0, 'entry': 100.0, 'sl_price': 99.0, 'side': 'buy', 'tp_order_id': 'existing_tp_123', 'tp_price': 105.0}}
        # SL order is missing on exchange, but TP is present
        self.mock_exchange.fetch_open_orders.return_value = [
            {'id': 'tp_123', 'symbol': 'TEST/USDT', 'type': 'take_profit_market', 'info': {'origType': 'TAKE_PROFIT_MARKET'}, 'stopPrice': 105.0, 'amount': 10.0, 'status': 'open'}
        ]
        
        self.mock_exchange.fetch_positions.return_value = [
            {'symbol': 'TEST/USDT', 'info': {'positionAmt': '10'}, 'entryPrice': 100.0}
        ]
        
        # When reconcile is called, it should create exactly ONE stop order
        self.mock_exchange.create_order.return_value = {'id': 'new_sl_123'}
        
        # Mocking check_position_status
        self.executor.check_position_status('TEST/USDT')
        
        # Verify create_order was called exactly once to restore the missing SL
        self.assertEqual(self.mock_exchange.create_order.call_count, 1)
        args, kwargs = self.mock_exchange.create_order.call_args
        self.assertEqual(args[0], 'TEST/USDT')
        self.assertEqual(args[1], 'STOP_MARKET')
        self.assertEqual(kwargs['params']['stopPrice'], 99.0)

if __name__ == '__main__':
    unittest.main()


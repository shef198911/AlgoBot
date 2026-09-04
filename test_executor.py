import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from executor import TraderExecutor
import config

class TestExecutor(unittest.TestCase):
    def setUp(self):
        # Disable logging to avoid console spam
        self.mock_logger = MagicMock()
        
        # Configure mock exchange
        self.mock_exchange = MagicMock()
        self.mock_exchange.markets = {'TEST/USDT': {}}
        self.mock_exchange.price_to_precision.side_effect = lambda sym, price: f"{price:.4f}"
        self.mock_exchange.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        
        self.executor = TraderExecutor(self.mock_exchange)
        self.executor.logger = self.mock_logger
        self.executor.risk_engine = MagicMock()
        
        # Override config dependencies
        config.MAX_CAPITAL_USDT = 1000.0
        config.LEVERAGE = 10
        config.STRUCTURE_RISK_ENABLED = True
        config.MAX_RISK_PERCENT = 1.0

    @patch('executor.json')
    @patch('executor.open')
    def test_01_execute_trade_success(self, mock_open, mock_json):
        # Mocks
        self.mock_exchange.create_market_order.return_value = {
            'id': 'market_id_123',
            'average': 101.0,
            'filled': 10.0
        }
        
        # Stop loss and take profit orders
        self.mock_exchange.create_order.side_effect = [
            {'id': 'sl_123'},
            {'id': 'tp_123'}
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
        self.assertEqual(pos['amount'], 10.0) # Check actual filled amount
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
            'filled': 10.0
        }
        
        # SL success, TP failure
        def create_order_side_effect(*args, **kwargs):
            if args[1] == 'STOP_MARKET':
                return {'id': 'sl_123'}
            elif args[1] == 'TAKE_PROFIT_MARKET':
                raise Exception("Network issue during TP")
                
        self.mock_exchange.create_order.side_effect = create_order_side_effect
        
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
        self.assertEqual(pos['amount'], 10.0)

if __name__ == '__main__':
    unittest.main()


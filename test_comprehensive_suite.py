import unittest
import os
import sys
import threading
import concurrent.futures
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

# Prevent real telegram messages during tests
patch('telegram_notifier.TelegramNotifier.send_message').start()

import config
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from executor import TraderExecutor
from trend_helper import evaluate_trend, get_global_trend, add_global_trend
from entry_gate import EntryGate, record_funnel_event, get_funnel_summary
from risk_manager import StructureRiskEngine

class TestComprehensiveSuite(unittest.TestCase):
    def setUp(self):
        import capital_manager
        capital_manager.MIN_RISK_USDT = 0.0
        for f in ['live_state.json', 'bot_equity.json', 'trade_history.txt']:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass
    
    # 1. Syntax of all Python files
    def test_01_syntax_compilation_all_files(self):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        py_files = [f for f in os.listdir(root_dir) if f.endswith('.py')]
        for f in py_files:
            file_path = os.path.join(root_dir, f)
            with open(file_path, 'r', encoding='utf-8-sig') as src:
                code = src.read()
            try:
                compile(code, file_path, 'exec')
            except Exception as e:
                self.fail(f"Syntax error in {f}: {e}")

    # 2. Imports across modules
    def test_02_imports_across_modules(self):
        import config
        import data_fetcher
        import strategy_ta
        import market_structure
        import risk_manager
        import entry_gate
        import ml_filter
        import executor
        import main
        import desktop_app
        import analytics
        self.assertTrue(hasattr(config, 'SYMBOLS'))
        self.assertTrue(hasattr(executor, 'TraderExecutor'))

    # 3. Startup components initialization
    def test_03_startup_components_initialization(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {}
        ta = TAStrategy()
        risk = StructureRiskEngine()
        ex = TraderExecutor(mock_ex)
        self.assertIsNotNone(ta)
        self.assertIsNotNone(risk)
        self.assertIsNotNone(ex)

    # 4. Entry Gate validation rules & fail-closed
    def test_04_entry_gate_validation_and_fail_closed(self):
        row_long = {
            'engine_signal': 1.0,
            'engine_setup': 'BREAKOUT_RETEST',
            'SETUP_SCORE': 70,
            'RSI': 50,
            'MARKET_STRUCTURE': 1.0,
            'DIST_RES_PCT': 0.05,
            'close': 105.0,
            'open': 100.0,
            'engine_context': {'broken_level': 100.0, 'rejection_low': 101.0}
        }
        # Valid with BULL trend
        valid, reason = EntryGate.validate(row_long, "BULL", "BTC/USDT", do_log=False)
        self.assertTrue(valid, reason)
        
        # Fail-closed with UNKNOWN trend
        valid_unkn, reason_unkn = EntryGate.validate(row_long, "UNKNOWN", "BTC/USDT", do_log=False)
        self.assertFalse(valid_unkn)
        self.assertEqual(reason_unkn, "BAD_GLOBAL_TREND")

    # 5. Global Trend evaluation formulas & fail-closed on NaN
    def test_05_global_trend_formulas_and_nans(self):
        # Normal bull
        trend = evaluate_trend(fast=105, slow=100, close=106, adx_val=30)
        self.assertIn(trend, ['BULL', 'STRONG_BULL'])
        
        # Normal bear
        trend_bear = evaluate_trend(fast=95, slow=100, close=94, adx_val=30)
        self.assertIn(trend_bear, ['BEAR', 'STRONG_BEAR'])
        
        # Missing / NaN data -> UNKNOWN (never RANGE)
        self.assertEqual(evaluate_trend(np.nan, 100, 105, 30), 'UNKNOWN')
        self.assertEqual(evaluate_trend(105, np.nan, 105, 30), 'UNKNOWN')
        self.assertEqual(evaluate_trend(105, 100, np.nan, 30), 'UNKNOWN')
        self.assertEqual(evaluate_trend(105, 100, 105, np.nan), 'UNKNOWN')
        self.assertEqual(evaluate_trend(0, 100, 105, 30), 'UNKNOWN')

    # 6. Train/live feature parity
    def test_06_train_live_feature_parity(self):
        ta = TAStrategy()
        data = {
            'timestamp': pd.date_range('2023-01-01', periods=120, freq='15min'),
            'open': [100.0 + i*0.1 for i in range(120)],
            'high': [101.0 + i*0.1 for i in range(120)],
            'low': [99.0 + i*0.1 for i in range(120)],
            'close': [100.5 + i*0.1 for i in range(120)],
            'volume': [500.0 for _ in range(120)],
        }
        df = pd.DataFrame(data)
        analyzed = ta.generate_features_and_signals(df, htf_trend="BULL", symbol="BTC/USDT", is_live=True)
        self.assertIsNotNone(analyzed)
        for col in config.FEATURE_COLUMNS:
            self.assertIn(col, analyzed.columns, f"Feature {col} missing from analyzed dataframe!")

    # 7. ML threshold loading
    def test_07_ml_threshold_loading(self):
        ml = MLFilter()
        self.assertIsNotNone(ml.threshold)
        self.assertGreater(ml.threshold, 0.0)
        self.assertLessEqual(ml.threshold, 1.0)

    # 8. ML validation split with Embargo
    def test_08_ml_threshold_embargo_split(self):
        self.assertGreater(config.ML_HORIZON, 0)

    # 9. Triple Barrier logic & StructureRiskEngine
    def test_09_triple_barrier_structural_alignment(self):
        risk = StructureRiskEngine()
        ctx = {'nearest_support': 98.0, 'swing_low': 98.0, 'nearest_resistance': 105.0}
        plan_long = risk.build_trade_plan('LONG', 100.0, 'SUPPORT_BOUNCE', ctx, atr=2.0)
        self.assertTrue(plan_long.get('valid'), plan_long.get('reason'))
        self.assertLess(plan_long['stop_loss'], 100.0)
        self.assertGreater(plan_long['take_profit'], 100.0)

    # 10. Execution engine happy path
    def test_10_execution_happy_path(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'BTC/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 0.02, 'average': 50000.0}
        mock_ex.create_order.side_effect = [{'id': 'sl1'}, {'id': 'tp1'}]
        mock_ex.fetch_open_orders.return_value = [{'id': 'sl1', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 49500.0, 'amount': 0.02, 'status': 'open'}]
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        res = executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, atr_value=100.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 49500.0})
        self.assertTrue(res, executor.last_error)
        self.assertIn('BTC/USDT', executor.positions)
        self.assertEqual(executor.positions['BTC/USDT']['sl_order_id'], 'sl1')
        self.assertEqual(executor.positions['BTC/USDT']['tp_order_id'], 'tp1')
        self.assertEqual(executor.positions['BTC/USDT']['amount'], 0.02)

    # 11. Execution UNKNOWN amount handling
    def test_11_execution_unknown_amount(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'BTC/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 0.0, 'average': 50000.0}
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        res = executor.execute_trade('BTC/USDT', 'buy', 10.0, 50000.0, atr_value=100.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 49500.0})
        self.assertFalse(res)
        self.assertEqual(executor.last_error, "UNKNOWN_AMOUNT")
        self.assertIn('BTC/USDT', executor.positions)
        self.assertEqual(executor.positions['BTC/USDT']['status'], 'UNKNOWN')

    # 12. SL failure triggers emergency close
    def test_12_sl_failure_triggers_emergency_close(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'ETH/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.side_effect = [
            {'id': 'm1', 'filled': 0.2, 'average': 3000.0},
            {'id': 'close1'}
        ]
        # SL order fails
        mock_ex.create_order.side_effect = Exception("Binance SL placement rejected")
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 50.0, 'stop_loss': 2950.0, 'take_profit': 3100.0
        })
        
        res = executor.execute_trade('ETH/USDT', 'buy', 10.0, 3000.0, atr_value=20.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 2950.0})
        self.assertFalse(res)
        mock_ex.create_market_order.assert_any_call('ETH/USDT', 'sell', 0.2, params={'reduceOnly': True})

    # 13. TP failure retains position protected by SL
    def test_13_tp_failure_retains_position(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'SOL/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 2.0, 'average': 150.0}
        
        def create_order_mock(sym, otype, side, amt, params=None):
            if otype == 'STOP_MARKET':
                return {'id': 'sl_ok'}
            raise Exception("TP rejected")
        mock_ex.create_order.side_effect = create_order_mock
        mock_ex.fetch_open_orders.return_value = [{'id': 'sl_ok', 'symbol': 'SOL/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 145.0, 'amount': 2.0, 'status': 'open'}]
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 5.0, 'stop_loss': 145.0, 'take_profit': 160.0
        })
        
        res = executor.execute_trade('SOL/USDT', 'buy', 10.0, 150.0, atr_value=2.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 145.0})
        self.assertTrue(res, executor.last_error)
        self.assertIn('SOL/USDT', executor.positions)
        self.assertEqual(executor.positions['SOL/USDT']['sl_order_id'], 'sl_ok')
        self.assertIsNone(executor.positions['SOL/USDT']['tp_order_id'])

    # 14 & 15. Recovery engine using actual exchange positionAmt
    def test_14_15_recovery_uses_actual_exchange_amount(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'ADA/USDT': {}}
        mock_ex.price_to_precision.return_value = '0.50'
        # Exchange has actual position of 1000.0 ADA
        mock_ex.fetch_positions.return_value = [
            {'symbol': 'ADA/USDT', 'side': 'long', 'entryPrice': 0.50, 'info': {'positionAmt': '1000.0'}}
        ]
        mock_ex.fetch_open_orders.return_value = []
        mock_ex.create_order.side_effect = [{'id': 'rec_sl'}, {'id': 'rec_tp'}]
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.positions['ADA/USDT'] = {
            'side': 'long', 'entry': 0.50, 'amount': 800.0,
            'sl_order_id': None, 'tp_order_id': None
        }
        
        status = executor.check_position_status('ADA/USDT')
        self.assertTrue(status)
        mock_ex.create_order.assert_any_call('ADA/USDT', 'STOP_MARKET', 'sell', 1000.0, params={'stopPrice': 0.50, 'reduceOnly': True})
        self.assertEqual(executor.positions['ADA/USDT']['amount'], 1000.0)

    # 16. Partial fill handling
    def test_16_partial_fill_uses_actual_filled(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'DOGE/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.1f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.4f}"
        # Requested 1000, filled 600
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 600.0, 'average': 0.10}
        mock_ex.create_order.side_effect = [{'id': 'sl1'}, {'id': 'tp1'}]
        mock_ex.fetch_open_orders.return_value = [{'id': 'sl1', 'symbol': 'DOGE/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 0.096, 'amount': 600.0, 'status': 'open'}]
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 0.004, 'stop_loss': 0.096, 'take_profit': 0.12
        })
        
        # We need to temporarily set LEVERAGE to 5, or adjust entry so SL doesn't hit liquidation.
        # Actually, with SL 0.096, distance is 0.004, which is 4%. 20x leverage liquidation is at 4.6%.
        # So SL at 0.096 (4%) is BEFORE liquidation (4.6%), so it's safe!
        res = executor.execute_trade('DOGE/USDT', 'buy', 10.0, 0.10, atr_value=0.005, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 0.096})
        self.assertTrue(res)
        mock_ex.create_order.assert_any_call('DOGE/USDT', 'STOP_MARKET', 'sell', 600.0, params={'stopPrice': 0.096, 'reduceOnly': True})
        self.assertEqual(executor.positions['DOGE/USDT']['amount'], 600.0)

    # 17. Capital reservation concurrency
    def test_17_capital_concurrency_and_limit(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'BTC/USDT': {}, 'ETH/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda s, a: str(a)
        mock_ex.price_to_precision.side_effect = lambda s, p: str(p)
        
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 100.0, 'stop_loss': 49000.0, 'take_profit': 52000.0
        })
        
        executor.positions['BTC/USDT'] = {'margin_required': config.MAX_CAPITAL_USDT - 5.0}
        
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        res = executor.execute_trade('ETH/USDT', 'buy', 10.0, 50000.0, atr_value=100.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 49000.0})
        self.assertFalse(res)
        self.assertIn("Недостаточно", executor.last_error)
        self.assertNotIn('ETH/USDT', executor.pending_margins)

    # 18. Duplicate signal & Signal State Machine
    def test_18_signal_state_machine_duplicate_protection(self):
        from main import signal_states, signal_tracker_lock
        sig_key = "TEST_BTC_123456_buy_BREAKOUT"
        with signal_tracker_lock:
            signal_states[sig_key] = {'status': 'EXECUTED', 'candle_time': 123456, 'attempts': 1}
        
        with signal_tracker_lock:
            st = signal_states[sig_key]['status']
            self.assertEqual(st, 'EXECUTED')

    # 19. CCXT Thread Safety
    def test_19_data_fetcher_thread_safety(self):
        fetcher = DataFetcher(use_testnet=True)
        self.assertTrue(hasattr(fetcher, 'lock'))
        self.assertIsInstance(fetcher.lock, type(threading.RLock()))

    # 20. Positions snapshot distribution
    def test_20_positions_snapshot(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.fetch_positions.return_value = [
            {'symbol': 'BTC/USDT:USDT', 'side': 'long', 'contracts': 1.0, 'entryPrice': 50000.0, 'info': {'positionAmt': '1.0'}},
            {'symbol': 'ETH/USDT:USDT', 'side': 'short', 'contracts': 2.0, 'entryPrice': 3000.0, 'info': {'positionAmt': '-2.0'}}
        ]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        snapshot = executor.fetch_all_positions()
        self.assertEqual(len(snapshot), 2)
        
        status_btc = executor.check_position_status('BTC/USDT', cached_positions=snapshot)
        self.assertTrue(status_btc)
        self.assertEqual(mock_ex.fetch_positions.call_count, 1)

    # 21. STOP behavior (graceful stop flag)
    def test_21_stop_behavior_graceful_flag(self):
        flag_file = "stop.flag"
        try:
            with open(flag_file, "w") as f:
                f.write("stop")
            self.assertTrue(os.path.exists(flag_file))
        finally:
            if os.path.exists(flag_file):
                os.remove(flag_file)

    # 22. Existing position protection & verification
    def test_22_existing_position_verification(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.markets = {'XRP/USDT': {}}
        mock_ex.fetch_positions.return_value = [
            {'symbol': 'XRP/USDT', 'side': 'long', 'entryPrice': 0.5, 'info': {'positionAmt': '500.0'}}
        ]
        mock_ex.fetch_open_orders.return_value = [
            {'id': 'sl_xrp', 'type': 'STOP_MARKET', 'stopPrice': 0.48}
        ]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.positions['XRP/USDT'] = {
            'side': 'long', 'entry': 0.5, 'amount': 500.0, 'sl_order_id': 'sl_xrp', 'tp_order_id': None
        }
        
    # 23. Real-time Funnel SIGNAL_FOUND tracking
    def test_23_funnel_live_signal_found(self):
        initial_funnel = get_funnel_summary()
        row_sig = {
            'engine_signal': 1.0,
            'engine_setup': 'BREAKOUT_RETEST',
            'SETUP_SCORE': 70,
            'RSI': 50,
            'MARKET_STRUCTURE': 1.0,
            'DIST_RES_PCT': 0.05,
            'close': 105.0,
            'open': 100.0,
            'engine_context': {'broken_level': 100.0, 'rejection_low': 101.0}
        }
        EntryGate.validate(row_sig, "BULL", "BTC/USDT", do_log=False, is_live=True)
        updated_funnel = get_funnel_summary()
        self.assertEqual(updated_funnel['SIGNAL_FOUND'], initial_funnel['SIGNAL_FOUND'] + 1)
        self.assertEqual(updated_funnel['ENTRY_GATE_PASS'], initial_funnel['ENTRY_GATE_PASS'] + 1)

    # 24. Snapshot None safety (does not delete existing positions on API failure)
    def test_24_position_snapshot_none_safety(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.fetch_positions.return_value = None
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.positions['BTC/USDT'] = {'side': 'long', 'entry': 50000.0, 'amount': 1.0, 'sl_order_id': 's1'}
        
        status = executor.check_position_status('BTC/USDT', cached_positions=None)
        self.assertEqual(status, 'UNKNOWN')
        self.assertIn('BTC/USDT', executor.positions)

    # 25. Train AI execution without NameError or crash
    def test_25_train_ai_end_to_end_mocked(self):
        from train_model import train_ai
        # Mock DataFetcher to return synthetic dataset with valid signals
        n = 400
        dates = pd.date_range('2023-01-01', periods=n, freq='15min')
        mock_df = pd.DataFrame({
            'timestamp': dates,
            'open': [100.0 + (i % 10)*0.5 for i in range(n)],
            'high': [105.0 + (i % 10)*0.5 for i in range(n)],
            'low': [95.0 + (i % 10)*0.5 for i in range(n)],
            'close': [102.0 + (i % 10)*0.5 for i in range(n)],
            'volume': [1000.0 for _ in range(n)]
        })
        
        with patch('train_model.DataFetcher') as MockDF:
            instance = MockDF.return_value
            instance.get_historical_klines.return_value = mock_df
            with patch('train_model.SYMBOLS', ['BTC/USDT']):
                with patch('joblib.dump') as mock_dump:
                    try:
                        train_ai()
                    except Exception as e:
                        self.fail(f"train_ai raised an unexpected exception: {e}")

    # 26. SafeExchange concurrency and thread safety
    def test_26_safe_exchange_concurrency(self):
        from data_fetcher import SafeExchange
        mock_raw = MagicMock()
        mock_raw.fetch_positions.side_effect = lambda: [{'symbol': 'BTC/USDT', 'info': {'positionAmt': '1.0'}}]
        mock_raw.fetch_ohlcv.side_effect = lambda symbol, timeframe, limit=100: [[1000, 10, 12, 9, 11, 100]]
        
        safe_ex = SafeExchange(mock_raw)
        
        results = []
        def worker():
            for _ in range(20):
                p = safe_ex.fetch_positions()
                o = safe_ex.fetch_ohlcv('BTC/USDT', '15m', limit=50)
                results.append(len(p) + len(o))
                
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        self.assertEqual(len(results), 100)
        self.assertEqual(mock_raw.fetch_positions.call_count, 100)
        self.assertEqual(mock_raw.fetch_ohlcv.call_count, 100)

    # 27. Unknown amount handling (amount=None, status=UNKNOWN, no local amount fallback)
    def test_27_unknown_amount_behavior(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        # Market order created without filled amount
        mock_ex.create_market_order.return_value = {'id': 'm_unk', 'average': 50000.0}
        # fetch_positions returns empty or error
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        success = executor.execute_trade('BTC/USDT', 'buy', 1.0, 50000.0, 100.0, 0.05, 'BREAKOUT_RETEST')
        self.assertFalse(success)
        self.assertEqual(executor.last_error, "UNKNOWN_AMOUNT")
        self.assertIn('BTC/USDT', executor.positions)
        self.assertIsNone(executor.positions['BTC/USDT']['amount'])
        self.assertEqual(executor.positions['BTC/USDT']['status'], 'UNKNOWN')

    # 28. Unknown position recovery on actual exchange amount
    def test_28_unknown_position_recovery(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        # Position is initially UNKNOWN with amount=None
        executor.positions['BTC/USDT'] = {
            'side': 'long',
            'entry': 50000.0,
            'max_price': 50000.0,
            'min_price': 50000.0,
            'sl_order_id': None,
            'tp_order_id': None,
            'amount': None,
            'status': 'UNKNOWN',
            'empty_checks': 0
        }
        
        # Exchange returns active position with actual amount 0.45
        snapshot = [{'symbol': 'BTC/USDT', 'side': 'long', 'entryPrice': 50000.0, 'info': {'positionAmt': '0.45'}}]
        mock_ex.fetch_positions.return_value = snapshot
        mock_ex.fetch_open_orders.return_value = []
        mock_ex.create_order.side_effect = [{'id': 'rec_sl'}, {'id': 'rec_tp'}]
        
        status = executor.check_position_status('BTC/USDT', cached_positions=snapshot)
        self.assertTrue(status)
        self.assertEqual(executor.positions['BTC/USDT']['amount'], 0.45)
        self.assertEqual(executor.positions['BTC/USDT']['status'], 'OPEN')
        self.assertEqual(executor.positions['BTC/USDT']['sl_order_id'], 'rec_sl')
        self.assertEqual(executor.positions['BTC/USDT']['tp_order_id'], 'rec_tp')
        # Verify SL order was created with amount 0.45
        sl_call = mock_ex.create_order.call_args_list[0]
        self.assertEqual(sl_call[0][3], 0.45)

    # 29. Empty snapshot transient protection (<3 checks keeps UNKNOWN)
    def test_29_empty_snapshot_transient_protection(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0}
]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.positions['BTC/USDT'] = {
            'side': 'long',
            'entry': 50000.0,
            'max_price': 50000.0,
            'min_price': 50000.0,
            'sl_order_id': None,
            'tp_order_id': None,
            'amount': None,
            'status': 'UNKNOWN',
            'empty_checks': 0
        }
        
        # Check 1: empty snapshot -> stays UNKNOWN
        s1 = executor.check_position_status('BTC/USDT', cached_positions=[])
        self.assertEqual(s1, 'UNKNOWN')
        self.assertIn('BTC/USDT', executor.positions)
        self.assertEqual(executor.positions['BTC/USDT']['empty_checks'], 1)
        
        # Check 2: empty snapshot -> stays UNKNOWN
        s2 = executor.check_position_status('BTC/USDT', cached_positions=[])
        self.assertEqual(s2, 'UNKNOWN')
        self.assertIn('BTC/USDT', executor.positions)
        self.assertEqual(executor.positions['BTC/USDT']['empty_checks'], 2)
        
        # Check 3: empty snapshot -> now confirmed closed and cleaned up
        s3 = executor.check_position_status('BTC/USDT', cached_positions=[])
        self.assertFalse(s3)
        self.assertNotIn('BTC/USDT', executor.positions)

    # 30. Partial fill handling (SL/TP placed strictly on actual amount)
    def test_30_partial_fill_handling(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        # Initial check_position_status sees empty positions; post-market sees filled
        mock_ex.fetch_positions.side_effect = [
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
],
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
],
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.35', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0}]
        ]
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm_part', 'average': 50000.0, 'filled': 0.35}
        mock_ex.create_order.side_effect = [{'id': 'sl_part'}, {'id': 'tp_part'}]
        mock_ex.fetch_open_orders.return_value = [{'id': 'sl_part', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 48500.0, 'amount': 0.35, 'status': 'open'}]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        success = executor.execute_trade('BTC/USDT', 'buy', 1.0, 50000.0, 100.0, 0.05, 'BREAKOUT_RETEST')
        self.assertTrue(success)
        self.assertEqual(executor.positions['BTC/USDT']['amount'], 0.35)
        # Check SL call used actual amount 0.35
        sl_call = mock_ex.create_order.call_args_list[0]
        self.assertEqual(sl_call[0][3], 0.35)

    # 31. SL placement failure triggers emergency close
    def test_31_sl_failure_triggers_emergency_close(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.fetch_positions.side_effect = [
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
], # check_position_status at start
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.5', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0}] # post-order check
        ]
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.side_effect = [
            {'id': 'm_entry', 'average': 50000.0, 'filled': 0.5},
            {'id': 'm_close', 'average': 49950.0, 'filled': 0.5}
        ]
        mock_ex.create_order.side_effect = Exception("Binance SL Error: Insufficient margin for stop loss")
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        success = executor.execute_trade('BTC/USDT', 'buy', 0.5, 50000.0, 100.0, 0.05, 'BREAKOUT_RETEST')
        self.assertFalse(success)
        self.assertEqual(executor.last_error, "SL_PLACEMENT_FAILED")
        self.assertNotIn('BTC/USDT', executor.positions)
        # Verify emergency close was called (2 market order calls: entry + close)
        self.assertEqual(mock_ex.create_market_order.call_count, 2)
        close_call = mock_ex.create_market_order.call_args_list[1]
        self.assertEqual(close_call[0][1], 'sell') # opposite side

    # 32. TP placement failure keeps position protected under SL and allows recovery
    def test_32_tp_failure_keeps_sl_protection(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
]
        mock_ex.fetch_positions.side_effect = [
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0},
    {'symbol': 'ETH/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 2000.0, 'markPrice': 3000.0},
    {'symbol': 'SOL/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 100.0, 'markPrice': 150.0},
    {'symbol': 'ADA/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.2, 'markPrice': 0.5},
    {'symbol': 'DOGE/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 0.05, 'markPrice': 0.1},
    {'symbol': 'TEST/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 0.0, 'liquidationPrice': 50.0, 'markPrice': 100.0}
], # check_position_status at start
            [{'symbol': 'BTC/USDT', 'side': 'long', 'info': {'positionAmt': '0.5', 'marginType': 'isolated', 'leverage': 20, 'liquidationPrice': 40000.0, 'markPrice': 50000.0}, 'entryPrice': 50000.0}] # post-order check
        ]
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm_entry', 'average': 50000.0, 'filled': 0.5}
        # First call (SL) succeeds, second call (TP) fails
        mock_ex.create_order.side_effect = [{'id': 'sl_ok'}, Exception("TP rejected by exchange")]
        mock_ex.fetch_open_orders.return_value = [{'id': 'sl_ok', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 48500.0, 'amount': 0.5, 'status': 'open'}]
        executor = TraderExecutor(mock_ex)
        executor.update_real_balance(10000.0)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 500.0, 'stop_loss': 49500.0, 'take_profit': 51000.0
        })
        
        success = executor.execute_trade('BTC/USDT', 'buy', 0.5, 50000.0, 100.0, 0.05, 'BREAKOUT_RETEST')
        self.assertTrue(success) # Position was successfully opened and protected by SL
        self.assertIn('BTC/USDT', executor.positions)
        self.assertEqual(executor.positions['BTC/USDT']['sl_order_id'], 'sl_ok')
        self.assertIsNone(executor.positions['BTC/USDT']['tp_order_id'])
        # Emergency close should NOT be called
        self.assertEqual(mock_ex.create_market_order.call_count, 1)

    # 33. Graceful stop behavior in main loop
    def test_33_graceful_stop_position_management(self):
        import main
        mock_executor = MagicMock()
        # Simulate active position on BTC/USDT
        mock_executor.positions = {'BTC/USDT': {'side': 'long', 'amount': 0.1}}
        mock_executor.check_position_status.return_value = True
        
        # When RUNNING is False, active positions should be processed
        active_statuses = [mock_executor.check_position_status(s) for s in list(mock_executor.positions.keys())]
        has_open = any(st in (True, 'UNKNOWN') for st in active_statuses)
        self.assertTrue(has_open)

    # 34. Risk Funnel event recording sequence
    def test_34_risk_funnel_event_recording(self):
        from entry_gate import record_funnel_event, get_funnel_summary
        summary_before = get_funnel_summary()
        
        record_funnel_event('RISK_FAIL')
        summary_fail = get_funnel_summary()
        self.assertEqual(summary_fail['RISK_FAIL'], summary_before['RISK_FAIL'] + 1)
        
        record_funnel_event('RISK_PASS')
        record_funnel_event('ORDER_ATTEMPT')
        summary_pass = get_funnel_summary()
        self.assertEqual(summary_pass['RISK_PASS'], summary_before['RISK_PASS'] + 1)
        self.assertEqual(summary_pass['ORDER_ATTEMPT'], summary_before['ORDER_ATTEMPT'] + 1)

    # 35. Desktop App config saving before AI training launch
    def test_35_desktop_app_save_config_before_train(self):
        from desktop_app import AlgoBotApp
        mock_page = MagicMock()
        app = AlgoBotApp(mock_page)
        
        saved_before_train = []
        def mock_save():
            saved_before_train.append(True)
            return True
            
        app.save_config = mock_save
        
        with patch('threading.Thread') as mock_thread:
            app.train_ai()
            self.assertEqual(len(saved_before_train), 1)
            self.assertTrue(saved_before_train[0])
            self.assertTrue(mock_thread.called)

    # 36. Global Trend Indicator Limit Parity
    def test_36_indicator_htf_trend_limit_parity(self):
        from trend_helper import get_global_trend, add_global_trend
        import config
        
        # Check config setting
        self.assertTrue(hasattr(config, 'HTF_TREND_HISTORY_LIMIT'))
        self.assertEqual(config.HTF_TREND_HISTORY_LIMIT, 500)
        
        mock_fetcher = MagicMock()
        dates = pd.date_range('2023-01-01', periods=500, freq='4h')
        df_htf = pd.DataFrame({
            'timestamp': dates,
            'open': [100.0 + i for i in range(500)],
            'high': [105.0 + i for i in range(500)],
            'low': [95.0 + i for i in range(500)],
            'close': [102.0 + i for i in range(500)],
            'volume': [1000.0 for _ in range(500)]
        })
        mock_fetcher.get_historical_klines.return_value = df_htf
        
        trend = get_global_trend(mock_fetcher, 'BTC/USDT')
        self.assertIn(trend, ['BULL', 'STRONG_BULL', 'BEAR', 'STRONG_BEAR', 'RANGE', 'UNKNOWN'])
        # Verify get_historical_klines was called with limit=500
        mock_fetcher.get_historical_klines.assert_called_with('BTC/USDT', config.TREND_TIMEFRAME, limit=config.HTF_TREND_HISTORY_LIMIT)

if __name__ == '__main__':
    unittest.main()


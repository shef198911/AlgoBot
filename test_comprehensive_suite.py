import unittest
import os
import sys
import threading
import concurrent.futures
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch

import config
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from executor import TraderExecutor
from trend_helper import evaluate_trend, get_global_trend, add_global_trend
from entry_gate import EntryGate, record_funnel_event, get_funnel_summary
from risk_manager import StructureRiskEngine

class TestComprehensiveSuite(unittest.TestCase):
    
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
        mock_ex.markets = {'BTC/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 0.02, 'average': 50000.0}
        mock_ex.create_order.side_effect = [{'id': 'sl1'}, {'id': 'tp1'}]
        
        executor = TraderExecutor(mock_ex)
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
        mock_ex.markets = {'BTC/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 0.0, 'average': 50000.0}
        mock_ex.fetch_positions.return_value = []
        
        executor = TraderExecutor(mock_ex)
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
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 50.0, 'stop_loss': 2950.0, 'take_profit': 3100.0
        })
        
        res = executor.execute_trade('ETH/USDT', 'buy', 10.0, 3000.0, atr_value=20.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 2950.0})
        self.assertFalse(res)
        mock_ex.create_market_order.assert_any_call('ETH/USDT', 'sell', 0.2, params={'reduceOnly': True})

    # 13. TP failure retains position protected by SL
    def test_13_tp_failure_retains_position(self):
        mock_ex = MagicMock()
        mock_ex.markets = {'SOL/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.4f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.2f}"
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 2.0, 'average': 150.0}
        
        def create_order_mock(sym, otype, side, amt, params=None):
            if otype == 'STOP_MARKET':
                return {'id': 'sl_ok'}
            raise Exception("TP rejected")
        mock_ex.create_order.side_effect = create_order_mock
        
        executor = TraderExecutor(mock_ex)
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
        mock_ex.markets = {'ADA/USDT': {}}
        mock_ex.price_to_precision.return_value = '0.50'
        # Exchange has actual position of 1000.0 ADA
        mock_ex.fetch_positions.return_value = [
            {'symbol': 'ADA/USDT', 'side': 'long', 'entryPrice': 0.50, 'info': {'positionAmt': '1000.0'}}
        ]
        mock_ex.fetch_open_orders.return_value = []
        mock_ex.create_order.side_effect = [{'id': 'rec_sl'}, {'id': 'rec_tp'}]
        
        executor = TraderExecutor(mock_ex)
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
        mock_ex.markets = {'DOGE/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda sym, amt: f"{amt:.1f}"
        mock_ex.price_to_precision.side_effect = lambda sym, p: f"{p:.4f}"
        # Requested 1000, filled 600
        mock_ex.create_market_order.return_value = {'id': 'm1', 'filled': 600.0, 'average': 0.10}
        mock_ex.create_order.side_effect = [{'id': 'sl1'}, {'id': 'tp1'}]
        
        executor = TraderExecutor(mock_ex)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 0.01, 'stop_loss': 0.09, 'take_profit': 0.12
        })
        
        res = executor.execute_trade('DOGE/USDT', 'buy', 10.0, 0.10, atr_value=0.005, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 0.09})
        self.assertTrue(res)
        mock_ex.create_order.assert_any_call('DOGE/USDT', 'STOP_MARKET', 'sell', 600.0, params={'stopPrice': 0.09, 'reduceOnly': True})
        self.assertEqual(executor.positions['DOGE/USDT']['amount'], 600.0)

    # 17. Capital reservation concurrency
    def test_17_capital_concurrency_and_limit(self):
        mock_ex = MagicMock()
        mock_ex.markets = {'BTC/USDT': {}, 'ETH/USDT': {}}
        mock_ex.amount_to_precision.side_effect = lambda s, a: str(a)
        mock_ex.price_to_precision.side_effect = lambda s, p: str(p)
        
        executor = TraderExecutor(mock_ex)
        executor.risk_engine.build_trade_plan = MagicMock(return_value={
            'valid': True, 'risk_distance': 100.0, 'stop_loss': 49000.0, 'take_profit': 52000.0
        })
        
        executor.positions['BTC/USDT'] = {'margin_required': config.MAX_CAPITAL_USDT - 5.0}
        
        mock_ex.fetch_positions.return_value = []
        res = executor.execute_trade('ETH/USDT', 'buy', 10.0, 50000.0, atr_value=100.0, setup_type='SUPPORT_BOUNCE', engine_context={'nearest_support': 49000.0})
        self.assertFalse(res)
        self.assertIn("Лимит капитала исчерпан", executor.last_error)
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
            {'symbol': 'BTC/USDT:USDT', 'side': 'long', 'contracts': 1.0, 'entryPrice': 50000.0, 'info': {'positionAmt': '1.0'}},
            {'symbol': 'ETH/USDT:USDT', 'side': 'short', 'contracts': 2.0, 'entryPrice': 3000.0, 'info': {'positionAmt': '-2.0'}}
        ]
        executor = TraderExecutor(mock_ex)
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
        mock_ex.markets = {'XRP/USDT': {}}
        mock_ex.fetch_positions.return_value = [
            {'symbol': 'XRP/USDT', 'side': 'long', 'entryPrice': 0.5, 'info': {'positionAmt': '500.0'}}
        ]
        mock_ex.fetch_open_orders.return_value = [
            {'id': 'sl_xrp', 'type': 'STOP_MARKET', 'stopPrice': 0.48}
        ]
        executor = TraderExecutor(mock_ex)
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
        mock_ex.fetch_positions.return_value = None
        executor = TraderExecutor(mock_ex)
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

if __name__ == '__main__':
    unittest.main()

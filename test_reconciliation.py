import unittest
import time
from unittest.mock import patch, MagicMock
from executor import TraderExecutor

class TestReconciliation(unittest.TestCase):
    def setUp(self):
        self.mock_exchange = MagicMock()
        self.mock_risk = MagicMock()
        self.executor = TraderExecutor(self.mock_exchange, self.mock_risk)
        self.executor._save_live_state = MagicMock()

    def test_a_ghost_state_removed_without_pnl(self):
        # A) exchange position ����������� + local ghost BTC ��� entry_order_id -> ������� local state, �� ��������� PnL.
        self.executor.positions['BTC/USDT'] = {
            'side': 'buy',
            'amount': 0.1,
            'entry': 50000,
            'entry_order_id': None,  # Ghost!
        }
        self.executor.capital_tracker = MagicMock()
        
        self.mock_exchange.fetch_positions.return_value = [] # No exchange positions
        self.mock_exchange.fetch_all_positions.return_value = []
        
        result = self.executor.check_position_status('BTC/USDT', force_fetch=True)
        
        self.assertFalse(result)
        self.assertNotIn('BTC/USDT', self.executor.positions)
        self.executor.capital_tracker.record_close.assert_not_called()

    def test_b_confirmed_entry_closed_correctly(self):
        # B) exchange position ����������� + �������������� entry + ����������� ������ -> ��������� ������� � ������� state.
        self.executor.positions['BTC/USDT'] = {
            'side': 'buy',
            'amount': 0.1,
            'entry': 50000,
            'entry_order_id': '12345',
            'empty_checks': 2, # force immediate closure branch
            'timestamp': time.time() * 1000 - 10000,
        }
        self.executor.capital_tracker = MagicMock()
        self.mock_exchange.fetch_positions.return_value = []
        self.mock_exchange.fetch_all_positions.return_value = []
        
        # Mock recent trades to provide PnL
        self.mock_exchange.fetch_my_trades.return_value = [
            {'side': 'sell', 'timestamp': time.time() * 1000, 'info': {'realizedPnl': '50.0'}, 'price': 50500}
        ]
        
        result = self.executor.check_position_status('BTC/USDT', force_fetch=True)
        
        self.assertFalse(result)
        self.assertNotIn('BTC/USDT', self.executor.positions)
        self.executor.capital_tracker.record_close.assert_called_once()
        args, kwargs = self.executor.capital_tracker.record_close.call_args
        self.assertEqual(args[0], 50.0)

    def test_c_pnl_unavailable_retries(self):
        # C) exchange position ����������� + �������������� entry, �� PnL �������� ���������� -> �� ��������� ����������
        self.executor.positions['BTC/USDT'] = {
            'side': 'buy',
            'amount': 0.1,
            'entry': 50000,
            'entry_order_id': '12345',
            'empty_checks': 2, # ready to close
            'timestamp': time.time() * 1000 - 10000,
            'reconciliation_retries': 0
        }
        self.executor.capital_tracker = MagicMock()
        self.mock_exchange.fetch_positions.return_value = []
        self.mock_exchange.fetch_all_positions.return_value = []
        self.mock_exchange.fetch_my_trades.return_value = [] # No trades, no SL price, PnL completely unknown
        
        # 1st retry
        res = self.executor.check_position_status('BTC/USDT', force_fetch=True)
        self.assertEqual(res, "UNKNOWN")
        self.assertIn('BTC/USDT', self.executor.positions)
        self.assertEqual(self.executor.positions['BTC/USDT']['reconciliation_retries'], 1)
        
        # 2nd retry
        self.executor.check_position_status('BTC/USDT', force_fetch=True)
        self.assertEqual(self.executor.positions['BTC/USDT']['reconciliation_retries'], 2)
        
        # 3rd retry
        self.executor.check_position_status('BTC/USDT', force_fetch=True)
        self.assertEqual(self.executor.positions['BTC/USDT']['reconciliation_retries'], 3)
        
        # 4th time -> gives up, removes state, no PnL
        res = self.executor.check_position_status('BTC/USDT', force_fetch=True)
        self.assertFalse(res)
        self.assertNotIn('BTC/USDT', self.executor.positions)
        self.executor.capital_tracker.record_close.assert_not_called()

    def test_d_restart_ghost_state_removed(self):
        # D) restart ����� �������� ghost state -> BTC �� ���������� �����.
        # Startup reconciliation ignores it, then check_position_status cleans it up.
        self.executor.positions['BTC/USDT'] = {
            'side': 'buy',
            'amount': 0.1,
            'entry': 50000,
            'entry_order_id': None,
        }
        self.mock_exchange.fetch_all_positions.return_value = []
        self.executor.reconcile_startup_positions()
        # It's still there after startup, but marked as ghost
        self.assertIn('BTC/USDT', self.executor.positions)
        
        # Check position status cleans it
        self.mock_exchange.fetch_positions.return_value = []
        self.executor.check_position_status('BTC/USDT', force_fetch=True)
        self.assertNotIn('BTC/USDT', self.executor.positions)

    def test_e_ghost_state_not_in_risk(self):
        # E) ���������, ��� ghost position �� ����������� � capital/margin/risk.
        # Actually risk is calculated using self.positions. 
        # But once check_position_status runs, it is immediately deleted and frees capital.
        self.executor.positions['BTC/USDT'] = {
            'side': 'buy',
            'amount': 0.1,
            'entry': 50000,
            'entry_order_id': None,
            'margin_required': 250.0
        }
        self.executor.pending_margins['BTC/USDT'] = 250.0
        
        self.mock_exchange.fetch_all_positions.return_value = []
        self.executor.check_position_status('BTC/USDT', force_fetch=True)
        
        self.assertNotIn('BTC/USDT', self.executor.positions)
        self.assertNotIn('BTC/USDT', self.executor.pending_margins)

if __name__ == "__main__":
    unittest.main()

import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_tests = """
    def test_37_sl_precision_truncates_risk(self):
        mock_ex = MagicMock()
        mock_ex.price_to_precision = lambda sym, p: f"{p:.2f}"
        mock_ex.amount_to_precision = lambda sym, a: f"{a:.4f}"
        
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        
        # Override exchange methods to pass checks
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 10}])
        
        # target: current_price=100, sl=90.0001 -> prec=90.00
        # risk_usdt=10, so amount = 10 / 10 = 1.0000
        # risk_usdt_actual = 1.0 * 10 = 10.0
        
        executor.calculate_sl_tp = MagicMock(return_value=(90.0001, 110.0))
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        
        plan = getattr(executor, 'last_trade_plan', {})
        self.assertEqual(plan.get('sl_price'), 90.0)
        self.assertEqual(plan.get('risk_distance'), 10.0)
        self.assertEqual(plan.get('risk_usdt_actual'), 10.0)

    def test_38_fee_recorded_once(self):
        from capital_manager import CapitalTracker
        tracker = CapitalTracker(100.0)
        tracker.record_fee(5.0, event_id="fee_123")
        self.assertEqual(tracker._total_fees, 5.0)
        tracker.record_fee(5.0, event_id="fee_123")
        self.assertEqual(tracker._total_fees, 5.0) # Should be idempotent

    def test_39_portfolio_risk_limit_strict(self):
        mock_ex = MagicMock()
        mock_ex.price_to_precision = lambda sym, p: f"{p:.2f}"
        mock_ex.amount_to_precision = lambda sym, a: f"{a:.4f}"
        
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 10}])
        
        # max portfolio risk is 15% -> 150
        executor.positions = {'DUMMY': {'status': 'OPEN', 'risk_usdt_actual': 145.0}}
        executor.calculate_sl_tp = MagicMock(return_value=(90.0, 110.0))
        
        # New trade risk = 10, total = 155 > 150
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertFalse(res)
        self.assertIn("Portfolio risk", str(executor.last_error))

    def test_40_startup_reconciliation(self):
        mock_ex = MagicMock()
        mock_ex.fetch_positions.return_value = [{'symbol': 'TEST/USDT', 'info': {'positionAmt': '10', 'leverage': 5}, 'entryPrice': 100}]
        
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        self.assertIn('TEST/USDT', executor.positions)
        self.assertEqual(executor.positions['TEST/USDT']['status'], 'UNKNOWN')

    def test_41_isolated_margin_fail_closed(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        
        # Return cross margin
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'cross', 'leverage': 10}])
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertFalse(res)
        self.assertIn("Isolated mode not confirmed", str(executor.last_error))

    def test_42_leverage_not_confirmed_fail_closed(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        
        # Missing leverage
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated'}])
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertFalse(res)
        self.assertIn("Leverage not confirmed", str(executor.last_error))

    def test_43_effective_capital_no_balance(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 10}])
        
        executor.get_effective_capital = MagicMock(return_value=0.0)
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertFalse(res)
        self.assertIn("effective_capital <= 0", str(executor.last_error))

    def test_44_pnl_zero_is_not_estimated(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.positions['TEST/USDT'] = {'side': 'buy', 'amount': 1.0, 'entry': 100.0}
        
        # Mock exchange positions to trigger close
        mock_ex.fetch_positions.return_value = []
        executor.fetch_all_positions = MagicMock(return_value=[])
        
        # Mock fetch_my_trades returning realizedPnl = 0
        mock_ex.fetch_my_trades = MagicMock(return_value=[{'side': 'sell', 'price': 100.0, 'info': {'realizedPnl': '0'}}])
        
        executor.capital_tracker.record_close = MagicMock()
        executor.check_position_status('TEST/USDT')
        
        executor.capital_tracker.record_close.assert_called_with(0.0, 0.0, event_id=unittest.mock.ANY, is_estimated=False)

    def test_45_post_fill_risk_violation_triggers_close(self):
        mock_ex = MagicMock()
        mock_ex.price_to_precision = lambda sym, p: f"{p:.2f}"
        mock_ex.amount_to_precision = lambda sym, a: f"{a:.4f}"
        
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 10}])
        executor.calculate_sl_tp = MagicMock(return_value=(90.0, 110.0))
        
        # Order returns normal
        mock_ex.create_market_order = MagicMock(return_value={'id': '1'})
        
        # BUT fetch_positions returns a giant amount
        executor.exchange.fetch_positions = MagicMock(return_value=[{'symbol': 'TEST/USDT', 'info': {'positionAmt': '100'}}]) # 100 coins
        
        executor.emergency_close = MagicMock()
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertFalse(res)
        executor.emergency_close.assert_called()

    def test_46_risk_usdt_actual_never_exceeds_requested(self):
        from capital_manager import calculate_position_size
        # Risk requested = 10, limit = 3% of 1000 = 30
        res = calculate_position_size(10.0, 10.0, 100.0, 10, 1000.0, 0.0, lambda x: round(x, 1))
        # Amount = 1.0 -> Risk = 10.0
        self.assertLessEqual(res['risk_usdt_actual'], 10.0)

    def test_47_tp_failure_safe(self):
        mock_ex = MagicMock()
        mock_ex.price_to_precision = lambda sym, p: f"{p:.2f}"
        mock_ex.amount_to_precision = lambda sym, a: f"{a:.4f}"
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 10}])
        executor.calculate_sl_tp = MagicMock(return_value=(90.0, 110.0))
        
        mock_ex.create_market_order = MagicMock(return_value={'id': '1'})
        executor.exchange.fetch_positions = MagicMock(return_value=[{'symbol': 'TEST/USDT', 'info': {'positionAmt': '1.0'}}])
        
        # Fail TP but SL succeeds
        def create_order_mock(sym, type, side, amt, params=None):
            if type == 'STOP_MARKET':
                return {'id': 'sl1'}
            else:
                raise Exception("TP Failed")
        mock_ex.create_order = create_order_mock
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        self.assertTrue(res)
        self.assertIn('TEST/USDT', executor.positions)

"""

# find class end and append
pattern = r"if __name__ == '__main__':"
content = content.replace("if __name__ == '__main__':", new_tests + "\nif __name__ == '__main__':")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added 11 robust tests to test_comprehensive_suite.py")

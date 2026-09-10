import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix test_37
t37_old = """    def test_37_sl_precision_truncates_risk(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        
        # Override exchange methods to pass checks
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 20}])"""
        
t37_new = """    def test_37_sl_precision_truncates_risk(self):
        mock_ex = MagicMock()
        import config
        config.LEVERAGE = 5
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        
        # Override exchange methods to pass checks
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 5}])"""

content = content.replace(t37_old, t37_new)

# Fix test_47
t47_old = """    def test_47_tp_failure_safe(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 20}])"""

t47_new = """    def test_47_tp_failure_safe(self):
        mock_ex = MagicMock()
        import config
        config.LEVERAGE = 5
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.capital_tracker.effective_capital = MagicMock(return_value=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        executor.get_effective_capital = MagicMock(return_value=1000.0)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 5}])"""

content = content.replace(t47_old, t47_new)

# also put it back to 20 at the end of the tests
content = content.replace("res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)\n        \n        plan", "res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)\n        config.LEVERAGE=20\n        plan")
content = content.replace("res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)\n        self.assertTrue(res)", "res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)\n        config.LEVERAGE=20\n        self.assertTrue(res)")

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)


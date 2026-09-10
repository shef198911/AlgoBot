import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_test = """
    def test_42b_leverage_mismatch_fail_closed(self):
        mock_ex = MagicMock()
        executor = TraderExecutor(mock_ex, working_capital=1000.0)
        executor.check_position_status = MagicMock(return_value=False)
        
        # Mismatch leverage (5 vs config 20)
        mock_ex.fapiPrivateV2GetPositionRisk = MagicMock(return_value=[{'marginType': 'isolated', 'leverage': 5}])
        
        # Mock set_leverage to simulate exception if needed, though it's optional
        mock_ex.set_leverage.side_effect = Exception("API")
        
        import config
        old_lev = config.LEVERAGE
        config.LEVERAGE = 20
        
        res = executor.execute_trade('TEST/USDT', 'buy', 10.0, 100.0)
        
        config.LEVERAGE = old_lev
        
        self.assertFalse(res)
        self.assertIn("Leverage mismatch", str(executor.last_error))
"""

if "test_42b_" not in content:
    content = content.replace("    def test_43_effective_capital_no_balance(self):", new_test + "\n    def test_43_effective_capital_no_balance(self):")
    with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
        f.write(content)

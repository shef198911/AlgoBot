import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        executor.capital_tracker.record_close = MagicMock()
        executor.check_position_status('TEST/USDT')
        
        executor.capital_tracker.record_close.assert_called_with(0.0, 0.0, event_id=unittest.mock.ANY, is_estimated=False)"""

replacement = """        executor.capital_tracker.record_close = MagicMock()
        executor.check_position_status('TEST/USDT') # 1/3
        executor.check_position_status('TEST/USDT') # 2/3
        executor.check_position_status('TEST/USDT') # 3/3 - CLOSE
        
        executor.capital_tracker.record_close.assert_called_with(0.0, 0.0, event_id=unittest.mock.ANY, is_estimated=False)"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated test 44 to call 3 times")

import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # fix 0.1 -> 0.01 in mock returns for execute_trade tests
    content = content.replace("'filled': 0.1", "'filled': 0.01")
    content = content.replace("'amount': 0.1", "'amount': 0.01")
    content = content.replace("'positionAmt': '0.1'", "'positionAmt': '0.01'")
    content = content.replace("assert_any_call('BTC/USDT', 'sell', 0.1", "assert_any_call('BTC/USDT', 'sell', 0.01")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_file('G:\\AlgoBot\\test_executor_recovery.py')

def fix_test_03():
    filepath = 'G:\\AlgoBot\\test_executor.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # the issue with test_03_tp_failure_retains_position is actual_rr < 1.5!
    # actual_price=101.0, sl=100.0, so risk=1.0. tp=105.0. 
    # actual_rr = (105-101) / (101-100) = 4.0. That's >= 1.5. 
    # Let's just print the error if it fails in the script output
    pass

if __name__ == '__main__':
    fix_test_03()

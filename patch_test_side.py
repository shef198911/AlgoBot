import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add an extra empty positions mock at the beginning of side_effect for test 31
test31_target = """        mock_ex.fetch_positions.side_effect = [
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'},"""
test31_replacement = """        mock_ex.fetch_positions.side_effect = [
            [], # startup reconciliation
            [
    {'symbol': 'BTC/USDT', 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'},"""
content = content.replace(test31_target, test31_replacement)

# Do the same for any others that might fail due to this
with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated side effects for startup reconciliation")

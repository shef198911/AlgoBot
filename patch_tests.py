import re

with open('test_entry_gate.py', 'r', encoding='utf-8') as f:
    eg_tests = f.read()

eg_tests = eg_tests.replace(
    "tests.append(('16', create_row(engine_signal=-1, engine_setup='RANGE_REJECTION', MARKET_STRUCTURE=0.0, close=95, open=100, engine_context={'rejection_high': 101}), 'RANGE', True, 'PASS'))",
    "tests.append(('16', create_row(engine_signal=-1, engine_setup='RANGE_REJECTION', MARKET_STRUCTURE=0.0, close=95, open=100, engine_context={'rejection_high': 101}), 'RANGE', True, 'PASS'))\n"
    "tests.append(('16b', create_row(engine_signal=-1, engine_setup='RESISTANCE_REJECTION', MARKET_STRUCTURE=0.0, close=95, open=100, engine_context={'rejection_high': 101}), 'RANGE', True, 'PASS'))\n"
    "tests.append(('16c', create_row(engine_signal=1, engine_setup='SUPPORT_BOUNCE', MARKET_STRUCTURE=0.0, engine_context={'rejection_low': 99}), 'RANGE', True, 'PASS'))"
)
with open('test_entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(eg_tests)
print("Updated test_entry_gate.py")

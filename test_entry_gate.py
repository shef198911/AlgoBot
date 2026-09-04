import pandas as pd
from entry_gate import EntryGate

def create_row(**kwargs):
    row = {
        'engine_signal': 0, 'engine_setup': 'None', 'SETUP_SCORE': 60,
        'RSI': 50, 'close': 105, 'open': 100,
        'MARKET_STRUCTURE': 1.0, 'DIST_RES_PCT': 0.05, 'DIST_SUP_PCT': 0.05,
        'SR_STRENGTH': 50.0,
        'engine_context': {}
    }
    for k, v in kwargs.items():
        if k == 'engine_context':
            row['engine_context'] = v
        else:
            row[k] = v
    return row

tests = []
# 1. BREAKOUT_RETEST без broken_level -> NO TRADE
tests.append(('1', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={}), 'BULL', False, 'NO_BROKEN_LEVEL'))
# 2. BREAKOUT_RETEST без confirmation -> NO TRADE
tests.append(('2', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={'broken_level': 100}), 'BULL', False, 'NO_BULLISH_CONFIRMATION'))
# 3. BREAKOUT_RETEST с confirmation -> PASS
tests.append(('3', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={'broken_level': 100, 'rejection_low': 99}), 'BULL', True, 'PASS'))

# 4. BREAKDOWN_RETEST без confirmation -> NO TRADE
tests.append(('4', create_row(engine_signal=-1, engine_setup='BREAKDOWN_RETEST', close=95, open=100, MARKET_STRUCTURE=-1.0, engine_context={'broken_level': 100}), 'BEAR', False, 'NO_BEARISH_CONFIRMATION'))
# 5. BREAKDOWN_RETEST с confirmation -> PASS
tests.append(('5', create_row(engine_signal=-1, engine_setup='BREAKDOWN_RETEST', close=95, open=100, MARKET_STRUCTURE=-1.0, engine_context={'broken_level': 100, 'rejection_high': 101}), 'BEAR', True, 'PASS'))

# 6. LIQUIDITY_SWEEP_LONG без sweep -> NO TRADE
tests.append(('6', create_row(engine_signal=1, engine_setup='LIQUIDITY_SWEEP_LONG', engine_context={'rejection_low': 99}), 'BULL', False, 'NO_REAL_SWEEP'))
# 7. LIQUIDITY_SWEEP_LONG без confirmation -> NO TRADE
tests.append(('7', create_row(engine_signal=1, engine_setup='LIQUIDITY_SWEEP_LONG', engine_context={'sweep_low': 98}), 'BULL', False, 'NO_BULLISH_CONFIRMATION'))
# 8. LIQUIDITY_SWEEP_LONG + sweep + confirmation -> PASS
tests.append(('8', create_row(engine_signal=1, engine_setup='LIQUIDITY_SWEEP_LONG', engine_context={'sweep_low': 98, 'rejection_low': 99}), 'BULL', True, 'PASS'))

# 9. LIQUIDITY_SWEEP_SHORT аналогично
tests.append(('9', create_row(engine_signal=-1, engine_setup='LIQUIDITY_SWEEP_SHORT', close=95, open=100, MARKET_STRUCTURE=-1.0, engine_context={'sweep_high': 102, 'rejection_high': 101}), 'BEAR', True, 'PASS'))

# 10. TREND_PULLBACK без structure -> NO TRADE
tests.append(('10', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=0.0, engine_context={'rejection_low': 99}), 'BULL', False, 'NO_BULLISH_STRUCTURE'))
# 11. TREND_PULLBACK + structure + confirmation -> PASS
tests.append(('11', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}), 'BULL', True, 'PASS'))

# 12. TREND_PULLBACK_DOWN без structure -> NO TRADE
tests.append(('12', create_row(engine_signal=-1, engine_setup='TREND_PULLBACK_DOWN', MARKET_STRUCTURE=0.0, close=95, open=100, engine_context={'rejection_high': 101}), 'BEAR', False, 'NO_BEARISH_STRUCTURE'))
# 13. TREND_PULLBACK_DOWN + structure + confirmation -> PASS
tests.append(('13', create_row(engine_signal=-1, engine_setup='TREND_PULLBACK_DOWN', MARKET_STRUCTURE=-1.0, close=95, open=100, engine_context={'rejection_high': 101}), 'BEAR', True, 'PASS'))

# 14. RANGE_BOUNCE без boundary reaction -> NO TRADE
tests.append(('14', create_row(engine_signal=1, engine_setup='RANGE_BOUNCE', MARKET_STRUCTURE=0.0, engine_context={}), 'RANGE', False, 'NO_BULLISH_CONFIRMATION'))
# 15. RANGE_BOUNCE + lower boundary + confirmation -> LONG
tests.append(('15', create_row(engine_signal=1, engine_setup='RANGE_BOUNCE', MARKET_STRUCTURE=0.0, engine_context={'rejection_low': 99}), 'RANGE', True, 'PASS'))

# 16. RANGE_REJECTION + upper boundary + confirmation -> SHORT
tests.append(('16', create_row(engine_signal=-1, engine_setup='RANGE_REJECTION', MARKET_STRUCTURE=0.0, close=95, open=100, engine_context={'rejection_high': 101}), 'RANGE', True, 'PASS'))

# 17. Score < MIN_SETUP_SCORE -> NO TRADE
tests.append(('17', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', SETUP_SCORE=54, MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}), 'BULL', False, 'LOW_SCORE'))

# 18. Strong opposite HTF trend -> NO TRADE
tests.append(('18', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}), 'BEAR', False, 'BAD_GLOBAL_TREND'))

# 19. Strong opposite S/R too close -> NO TRADE (checking SR Quality scaling)
tests.append(('19', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, SR_STRENGTH=100.0, DIST_RES_PCT=0.003, engine_context={'rejection_low': 99}), 'BULL', False, 'RESISTANCE_TOO_CLOSE'))

passed = 0
for name, r, htf_trend, exp_sig, exp_reason in tests:
    is_valid, reason = EntryGate.validate(r, htf_trend, "TEST")
    if is_valid == exp_sig and reason == exp_reason:
        passed += 1
    else:
        print(f"Test {name} FAILED! Expected {exp_sig} ({exp_reason}), got {is_valid} ({reason})")

print(f"ENTRY GATE VERIFICATION")
print(f"{passed}/{len(tests)} PASS")


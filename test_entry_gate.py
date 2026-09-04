import pandas as pd

MIN_SETUP_SCORE = 55
min_sr = 0.005

def get_global_trend(row):
    fast = row.get('EMA_FAST', 0)
    slow = row.get('EMA_SLOW', 0)
    close = row.get('close', 0)
    adx = row.get('ADX', 0)
    
    if pd.isna(fast) or pd.isna(slow) or slow == 0:
        return "RANGE"
        
    ema_dist = (fast - slow) / slow
    
    if fast > slow and close > fast:
        if adx > 25 and ema_dist > 0.002:
            return "STRONG_BULL"
        else:
            return "BULL"
    elif fast < slow and close < fast:
        if adx > 25 and ema_dist < -0.002:
            return "STRONG_BEAR"
        else:
            return "BEAR"
    else:
        return "RANGE"

class DummyLogger:
    def info(self, msg):
        pass

dummy_logger = DummyLogger()
self = type('obj', (object,), {'current_symbol': 'TEST', 'logger': dummy_logger})()

def get_confirmed_signal(row):
    eng_sig = row.get('engine_signal', 0)
    eng_setup = row.get('engine_setup', 'None')
    score = row.get('SETUP_SCORE', 0)
    rsi = row.get('RSI', 50)
    
    if eng_sig == 0 or eng_setup == "None":
        return 0, "None", "NO_SIGNAL"
        
    ctx = row.get('engine_context', {})
    if not isinstance(ctx, dict):
        ctx = {}
        
    global_trend = row.get('GLOBAL_TREND', 'RANGE')
    
    mandatory_pass = False
    reject_reason = "NO_REASON"
    
    struct_val = row.get('MARKET_STRUCTURE', 0)
    is_bullish_struct = (struct_val == 1.0)
    is_bearish_struct = (struct_val == -1.0)
    
    if eng_sig == 1.0: # LONG
        if eng_setup == "BREAKOUT_RETEST":
            if ctx.get('broken_level') is None:
                reject_reason = "NO_BROKEN_LEVEL"
            elif not ctx.get('rejection_low'):
                reject_reason = "NO_BULLISH_CONFIRMATION"
            elif is_bearish_struct:
                reject_reason = "BEARISH_STRUCTURE"
            elif global_trend not in ['BULL', 'STRONG_BULL']:
                reject_reason = "BAD_GLOBAL_TREND"
            elif row.get('close', 0) <= row.get('open', 0):
                reject_reason = "RED_CANDLE_CLOSE"
            else:
                mandatory_pass = True
                
        elif eng_setup == "LIQUIDITY_SWEEP":
            if not ctx.get('sweep_low'):
                reject_reason = "NO_REAL_SWEEP"
            elif not ctx.get('rejection_low'):
                reject_reason = "NO_BULLISH_CONFIRMATION"
            elif is_bearish_struct:
                reject_reason = "BEARISH_STRUCTURE"
            elif global_trend not in ['BULL', 'STRONG_BULL']:
                reject_reason = "BAD_GLOBAL_TREND"
            else:
                mandatory_pass = True
                
        elif eng_setup == "TREND_PULLBACK":
            if not is_bullish_struct:
                reject_reason = "NO_BULLISH_STRUCTURE"
            elif not ctx.get('rejection_low'):
                reject_reason = "NO_BULLISH_CONFIRMATION"
            elif global_trend not in ['BULL', 'STRONG_BULL']:
                reject_reason = "BAD_GLOBAL_TREND"
            else:
                mandatory_pass = True
                
        elif eng_setup == "RANGE_BOUNCE":
            if not ctx.get('rejection_low'):
                reject_reason = "NO_BULLISH_CONFIRMATION"
            elif is_bullish_struct or is_bearish_struct:
                reject_reason = "NOT_IN_RANGE_STRUCTURE"
            else:
                mandatory_pass = True
        else:
            reject_reason = "UNKNOWN_SETUP"

        if mandatory_pass:
            if score < MIN_SETUP_SCORE:
                mandatory_pass = False
                reject_reason = "LOW_SCORE"
            elif row.get('DIST_RES_PCT', 1.0) < min_sr:
                mandatory_pass = False
                reject_reason = "RESISTANCE_TOO_CLOSE"
            elif rsi > 75:
                mandatory_pass = False
                reject_reason = "RSI_OVERBOUGHT"

    elif eng_sig == -1.0: # SHORT
        if eng_setup == "BREAKDOWN_RETEST":
            if ctx.get('broken_level') is None:
                reject_reason = "NO_BROKEN_LEVEL"
            elif not ctx.get('rejection_high'):
                reject_reason = "NO_BEARISH_CONFIRMATION"
            elif is_bullish_struct:
                reject_reason = "BULLISH_STRUCTURE"
            elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                reject_reason = "BAD_GLOBAL_TREND"
            elif row.get('close', 0) >= row.get('open', 0):
                reject_reason = "GREEN_CANDLE_CLOSE"
            else:
                mandatory_pass = True
                
        elif eng_setup == "LIQUIDITY_SWEEP":
            if not ctx.get('sweep_high'):
                reject_reason = "NO_REAL_SWEEP"
            elif not ctx.get('rejection_high'):
                reject_reason = "NO_BEARISH_CONFIRMATION"
            elif is_bullish_struct:
                reject_reason = "BULLISH_STRUCTURE"
            elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                reject_reason = "BAD_GLOBAL_TREND"
            else:
                mandatory_pass = True
                
        elif eng_setup == "TREND_PULLBACK":
            if not is_bearish_struct:
                reject_reason = "NO_BEARISH_STRUCTURE"
            elif not ctx.get('rejection_high'):
                reject_reason = "NO_BEARISH_CONFIRMATION"
            elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                reject_reason = "BAD_GLOBAL_TREND"
            else:
                mandatory_pass = True
                
        elif eng_setup == "RANGE_BOUNCE":
            if not ctx.get('rejection_high'):
                reject_reason = "NO_BEARISH_CONFIRMATION"
            elif is_bullish_struct or is_bearish_struct:
                reject_reason = "NOT_IN_RANGE_STRUCTURE"
            else:
                mandatory_pass = True
        else:
            reject_reason = "UNKNOWN_SETUP"

        if mandatory_pass:
            if score < MIN_SETUP_SCORE:
                mandatory_pass = False
                reject_reason = "LOW_SCORE"
            elif row.get('DIST_SUP_PCT', 1.0) < min_sr:
                mandatory_pass = False
                reject_reason = "SUPPORT_TOO_CLOSE"
            elif rsi < 25:
                mandatory_pass = False
                reject_reason = "RSI_OVERSOLD"

    if not mandatory_pass:
        return 0, "None", reject_reason
        
    return eng_sig, eng_setup, "PASS"

def create_row(**kwargs):
    row = {
        'engine_signal': 0, 'engine_setup': 'None', 'SETUP_SCORE': 60,
        'RSI': 50, 'EMA_FAST': 100, 'EMA_SLOW': 90, 'close': 105, 'open': 100,
        'ADX': 30, 'MARKET_STRUCTURE': 1.0, 'DIST_RES_PCT': 0.05, 'DIST_SUP_PCT': 0.05,
        'engine_context': {}
    }
    for k, v in kwargs.items():
        if k == 'engine_context':
            row['engine_context'] = v
        else:
            row[k] = v
    
    row['GLOBAL_TREND'] = get_global_trend(row)
    return row

tests = []
tests.append(('1', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={'broken_level': 100}), 0, 'NO_BULLISH_CONFIRMATION'))
tests.append(('2', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={'broken_level': 100, 'rejection_low': 99}), 1, 'PASS'))
tests.append(('3', create_row(engine_signal=1, engine_setup='LIQUIDITY_SWEEP', engine_context={'sweep_low': 98}), 0, 'NO_BULLISH_CONFIRMATION'))
tests.append(('4', create_row(engine_signal=1, engine_setup='LIQUIDITY_SWEEP', engine_context={'sweep_low': 98, 'rejection_low': 99}), 1, 'PASS'))
tests.append(('5', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=0.0, engine_context={'rejection_low': 99}), 0, 'NO_BULLISH_STRUCTURE'))
tests.append(('6', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}), 1, 'PASS'))
tests.append(('7', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', DIST_RES_PCT=0.001, engine_context={'broken_level': 100, 'rejection_low': 99}), 0, 'RESISTANCE_TOO_CLOSE'))
tests.append(('8', create_row(engine_signal=-1, engine_setup='BREAKDOWN_RETEST', MARKET_STRUCTURE=-1.0, EMA_FAST=90, EMA_SLOW=100, close=85, open=90, DIST_SUP_PCT=0.001, engine_context={'broken_level': 100, 'rejection_high': 101}), 0, 'SUPPORT_TOO_CLOSE'))
tests.append(('9', create_row(engine_signal=1, engine_setup='RANGE_BOUNCE', MARKET_STRUCTURE=0.0, EMA_FAST=100, EMA_SLOW=100, close=100, open=95, engine_context={}), 0, 'NO_BULLISH_CONFIRMATION'))
tests.append(('10', create_row(engine_signal=1, engine_setup='RANGE_BOUNCE', MARKET_STRUCTURE=0.0, EMA_FAST=100, EMA_SLOW=100, close=100, open=95, engine_context={'rejection_low': 99}), 1, 'PASS'))
tests.append(('11', create_row(engine_signal=-1, engine_setup='RANGE_BOUNCE', MARKET_STRUCTURE=0.0, EMA_FAST=100, EMA_SLOW=100, close=95, open=100, engine_context={'rejection_high': 101}), -1, 'PASS'))
tests.append(('12', create_row(engine_signal=1, engine_setup='CHOCH_LONG'), 0, 'UNKNOWN_SETUP'))
tests.append(('13', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', SETUP_SCORE=55, MARKET_STRUCTURE=1.0, engine_context={}), 0, 'NO_BULLISH_CONFIRMATION'))
tests.append(('14', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', SETUP_SCORE=55, MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}), 1, 'PASS'))
tests.append(('15', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, EMA_FAST=90, EMA_SLOW=100, close=85, open=80, engine_context={'rejection_low': 99}), 0, 'BAD_GLOBAL_TREND'))
tests.append(('16', create_row(engine_signal=1, engine_setup='BREAKOUT_RETEST', engine_context={'broken_level': 100, 'rejection_low': 99}, close=105, open=110), 0, 'RED_CANDLE_CLOSE'))
tests.append(('17', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}, SETUP_SCORE=54), 0, 'LOW_SCORE'))
tests.append(('18', create_row(engine_signal=1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=1.0, engine_context={'rejection_low': 99}, RSI=76), 0, 'RSI_OVERBOUGHT'))
tests.append(('19', create_row(engine_signal=-1, engine_setup='TREND_PULLBACK', MARKET_STRUCTURE=-1.0, EMA_FAST=90, EMA_SLOW=100, close=85, open=90, engine_context={'rejection_high': 101}, RSI=20), 0, 'RSI_OVERSOLD'))
tests.append(('20', create_row(engine_signal=-1, engine_setup='LIQUIDITY_SWEEP', MARKET_STRUCTURE=-1.0, EMA_FAST=90, EMA_SLOW=100, close=85, open=90, engine_context={'sweep_high': 110, 'rejection_high': 101}), -1, 'PASS'))

passed = 0
for name, r, exp_sig, exp_reason in tests:
    sig, setup, reason = get_confirmed_signal(r)
    if sig == exp_sig and reason == exp_reason:
        passed += 1
    else:
        print(f"Test {name} FAILED! Expected {exp_sig} ({exp_reason}), got {sig} ({reason})")

print(f"ENTRY GATE VERIFICATION")
print(f"{passed}/{len(tests)} PASS")


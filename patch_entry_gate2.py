import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

start_marker = 'def get_confirmed_signal(row):'
end_marker = 'results = [get_confirmed_signal(row) for _, row in data.iterrows()]'

new_code = '''            def get_global_trend(row):
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

            def get_confirmed_signal(row):
                eng_sig = row.get('engine_signal', 0)
                eng_setup = row.get('engine_setup', 'None')
                score = row.get('SETUP_SCORE', 0)
                rsi = row.get('RSI', 50)
                
                if eng_sig == 0 or eng_setup == "None":
                    return 0, "None"
                    
                ctx = row.get('engine_context', {})
                if not isinstance(ctx, dict):
                    ctx = {}
                    
                global_trend = get_global_trend(row)
                
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
                    # Log rejection
                    symbol_str = getattr(self, "current_symbol", "UNKNOWN")
                    direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
                    
                    self.logger.info(
                        f"\\n[ENTRY CHECK REJECT]\\n"
                        f"SYMBOL={symbol_str} {direction_str}\\n"
                        f"SETUP={eng_setup}\\n"
                        f"SCORE={score}\\n"
                        f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                        f"GLOBAL_TREND={global_trend}\\n"
                        f"ENTRY_GATE=FAIL\\n"
                        f"REASON={reject_reason}\\n"
                    )
                    return 0, "None"
                    
                symbol_str = getattr(self, "current_symbol", "UNKNOWN")
                direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
                self.logger.info(
                    f"\\n[ENTRY CHECK PASS]\\n"
                    f"SYMBOL={symbol_str} {direction_str}\\n"
                    f"SETUP={eng_setup}\\n"
                    f"SCORE={score}\\n"
                    f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                    f"GLOBAL_TREND={global_trend}\\n"
                    f"ENTRY_GATE=PASS\\n"
                )
                return eng_sig, eng_setup
'''

s = source.find(start_marker)
e = source.find(end_marker)

source = source[:s] + new_code + '\n            ' + source[e:]

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

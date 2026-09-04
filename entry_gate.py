LOG_ENTRY_GATE = True
import pandas as pd
from config import MIN_SR_DISTANCE_PCT, MIN_SETUP_SCORE, logger

# Global entry statistics
last_logged_reject = {}

entry_stats = {
    'TA_CANDIDATES': 0,
    'ENTRY_GATE_PASS': 0,
    'REJECT_NO_BROKEN_LEVEL': 0,
    'REJECT_NO_CONFIRMATION': 0,
    'REJECT_BAD_STRUCTURE': 0,
    'REJECT_BAD_GLOBAL_TREND': 0,
    'REJECT_CANDLE_CLOSE': 0,
    'REJECT_NO_REAL_SWEEP': 0,
    'REJECT_NOT_IN_RANGE': 0,
    'REJECT_UNKNOWN_SETUP': 0,
    'REJECT_LOW_SCORE': 0,
    'REJECT_SR_TOO_CLOSE': 0,
    'REJECT_RSI_EXTREME': 0
}

class EntryGate:
    @staticmethod
    def validate(row, global_trend, symbol="UNKNOWN", do_log=True):
        eng_sig = row.get('engine_signal', 0)
        eng_setup = row.get('engine_setup', 'None')
        score = row.get('SETUP_SCORE', 0)
        rsi = row.get('RSI', 50)
        
        if eng_sig == 0 or eng_setup == "None":
            return False, "NO_SIGNAL"
            
        entry_stats['TA_CANDIDATES'] += 1
            
        ctx = row.get('engine_context', {})
        if not isinstance(ctx, dict):
            ctx = {}
            
        mandatory_pass = False
        reject_reason = "NO_REASON"
        
        struct_val = row.get('MARKET_STRUCTURE', 0)
        is_bullish_struct = (struct_val == 1.0)
        is_bearish_struct = (struct_val == -1.0)
        
        min_sr = MIN_SR_DISTANCE_PCT
        sr_strength = row.get('SR_STRENGTH', 50.0)
        req_dist = min_sr * max(1.0, (sr_strength / 50.0))
        
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
                    
            elif eng_setup == "LIQUIDITY_SWEEP_LONG":
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
                    
            elif eng_setup in ["RANGE_BOUNCE", "SUPPORT_BOUNCE"]:
                if not ctx.get('rejection_low'):
                    reject_reason = "NO_BULLISH_CONFIRMATION"
                elif is_bullish_struct or is_bearish_struct:
                    reject_reason = "NOT_IN_RANGE_STRUCTURE"
                elif global_trend != "RANGE":
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
            else:
                reject_reason = "UNKNOWN_SETUP"

            if mandatory_pass:
                if score < MIN_SETUP_SCORE:
                    mandatory_pass = False
                    reject_reason = "LOW_SCORE"
                elif row.get('DIST_RES_PCT', 1.0) < req_dist:
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
                    
            elif eng_setup == "LIQUIDITY_SWEEP_SHORT":
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
                    
            elif eng_setup == "TREND_PULLBACK_DOWN":
                if not is_bearish_struct:
                    reject_reason = "NO_BEARISH_STRUCTURE"
                elif not ctx.get('rejection_high'):
                    reject_reason = "NO_BEARISH_CONFIRMATION"
                elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup in ["RANGE_REJECTION", "RESISTANCE_REJECTION"]:
                if not ctx.get('rejection_high'):
                    reject_reason = "NO_BEARISH_CONFIRMATION"
                elif is_bullish_struct or is_bearish_struct:
                    reject_reason = "NOT_IN_RANGE_STRUCTURE"
                elif global_trend != "RANGE":
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
            else:
                reject_reason = "UNKNOWN_SETUP"

            if mandatory_pass:
                if score < MIN_SETUP_SCORE:
                    mandatory_pass = False
                    reject_reason = "LOW_SCORE"
                elif row.get('DIST_SUP_PCT', 1.0) < req_dist:
                    mandatory_pass = False
                    reject_reason = "SUPPORT_TOO_CLOSE"
                elif rsi < 25:
                    mandatory_pass = False
                    reject_reason = "RSI_OVERSOLD"

        if not mandatory_pass:
            if "BROKEN_LEVEL" in reject_reason: entry_stats['REJECT_NO_BROKEN_LEVEL'] += 1
            elif "CONFIRMATION" in reject_reason: entry_stats['REJECT_NO_CONFIRMATION'] += 1
            elif "STRUCTURE" in reject_reason: entry_stats['REJECT_BAD_STRUCTURE'] += 1
            elif "GLOBAL_TREND" in reject_reason: entry_stats['REJECT_BAD_GLOBAL_TREND'] += 1
            elif "CANDLE" in reject_reason: entry_stats['REJECT_CANDLE_CLOSE'] += 1
            elif "SWEEP" in reject_reason: entry_stats['REJECT_NO_REAL_SWEEP'] += 1
            elif "SCORE" in reject_reason: entry_stats['REJECT_LOW_SCORE'] += 1
            elif "CLOSE" in reject_reason: entry_stats['REJECT_SR_TOO_CLOSE'] += 1
            elif "RSI" in reject_reason: entry_stats['REJECT_RSI_EXTREME'] += 1
            else: entry_stats['REJECT_UNKNOWN_SETUP'] += 1
            
            direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
            
            if LOG_ENTRY_GATE and do_log:
                logger.info(
                    f"\\n[ENTRY CHECK REJECT]\\n"
                    f"SYMBOL={symbol} {direction_str}\\n"
                    f"SETUP={eng_setup}\\n"
                    f"SCORE={score}\\n"
                    f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                    f"GLOBAL_TREND={global_trend}\\n"
                    f"ENTRY_GATE=FAIL\\n"
                    f"REASON={reject_reason}\\n"
                )
            return False, reject_reason
            
        entry_stats['ENTRY_GATE_PASS'] += 1
        direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
        if LOG_ENTRY_GATE and do_log:
            logger.info(
                f"\\n[ENTRY CHECK PASS]\\n"
                f"SYMBOL={symbol} {direction_str}\\n"
                f"SETUP={eng_setup}\\n"
                f"SCORE={score}\\n"
                f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                f"GLOBAL_TREND={global_trend}\\n"
                f"ENTRY_GATE=PASS\\n"
            )
        return True, "PASS"


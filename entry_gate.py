LOG_ENTRY_GATE = True
import pandas as pd
import threading
from config import MIN_SR_DISTANCE_PCT, MIN_SETUP_SCORE, logger
from diagnostic_tracker import diagnostic_tracker

# Global entry statistics & Real-time Signal Funnel
last_logged_reject = {}
stats_lock = threading.Lock()

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

entry_funnel = {
    'SIGNAL_FOUND': 0,
    'GLOBAL_TREND_PASS': 0,
    'GLOBAL_TREND_FAIL': 0,
    'STRUCTURE_PASS': 0,
    'STRUCTURE_FAIL': 0,
    'CONFIRMATION_PASS': 0,
    'CONFIRMATION_FAIL': 0,
    'ENTRY_GATE_PASS': 0,
    'ENTRY_GATE_FAIL': 0,
    'ML_PASS': 0,
    'ML_FAIL': 0,
    'RISK_PASS': 0,
    'RISK_FAIL': 0,
    'ORDER_ATTEMPT': 0,
    'ORDER_SUCCESS': 0,
    'ORDER_FAIL': 0
}

entry_funnel_by_setup = {}
entry_reject_by_reason = {}

def record_entry_result(setup, direction, passed, reason=None):
    key = f"{setup}:{direction}"

    with stats_lock:
        item = entry_funnel_by_setup.setdefault(
            key,
            {
                "candidates": 0,
                "passed": 0,
                "rejected": {}
            }
        )

        item["candidates"] += 1

        if passed:
            item["passed"] += 1
        else:
            item["rejected"][reason or "UNKNOWN"] = (
                item["rejected"].get(reason or "UNKNOWN", 0) + 1
            )
            entry_reject_by_reason[reason or "UNKNOWN"] = (
                entry_reject_by_reason.get(reason or "UNKNOWN", 0) + 1
            )

def get_detailed_funnel():
    with stats_lock:
        return {
            "global": dict(entry_funnel),
            "by_setup": {
                k: {
                    "candidates": v["candidates"],
                    "passed": v["passed"],
                    "rejected": dict(v["rejected"])
                }
                for k, v in entry_funnel_by_setup.items()
            },
            "reject_reasons": dict(entry_reject_by_reason)
        }

def record_funnel_event(event_name: str, count: int = 1):
    with stats_lock:
        if event_name in entry_funnel:
            entry_funnel[event_name] += count

def get_funnel_summary() -> dict:
    from diagnostic_tracker import get_signal_funnel_report
    # Return both the old dict and we can print the new report
    print(get_signal_funnel_report())
    with stats_lock:
        return dict(entry_funnel)

class EntryGate:
    @staticmethod
    def validate(row, global_trend, symbol="UNKNOWN", do_log=True, is_live=False):
        eng_sig = row.get('engine_signal', 0)
        eng_setup = row.get('engine_setup', 'None')
        score = row.get('SETUP_SCORE', 0)
        rsi = row.get('RSI', 50)
        
        if eng_sig == 0 or eng_setup == "None":
            return False, "NO_SIGNAL"
            
        direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
            
        if is_live:
            diagnostic_tracker.record_ta_signal(symbol, direction_str)
            with stats_lock:
                entry_stats['TA_CANDIDATES'] += 1
                entry_funnel['SIGNAL_FOUND'] += 1
            
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
                if global_trend not in ['BULL', 'STRONG_BULL']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup == "LIQUIDITY_SWEEP_LONG":
                if global_trend not in ['BULL', 'STRONG_BULL']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup == "TREND_PULLBACK":
                if global_trend not in ['BULL', 'STRONG_BULL']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup in ["RANGE_BOUNCE", "SUPPORT_BOUNCE"]:
                if global_trend == "STRONG_BEAR":
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
                if global_trend not in ['BEAR', 'STRONG_BEAR']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup == "LIQUIDITY_SWEEP_SHORT":
                if global_trend not in ['BEAR', 'STRONG_BEAR']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup == "TREND_PULLBACK_DOWN":
                if global_trend not in ['BEAR', 'STRONG_BEAR']:
                    reject_reason = "BAD_GLOBAL_TREND"
                else:
                    mandatory_pass = True
                    
            elif eng_setup in ["RANGE_REJECTION", "RESISTANCE_REJECTION"]:
                if global_trend == "STRONG_BULL":
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
            if is_live:
                if "GLOBAL_TREND" in reject_reason:
                    diagnostic_tracker.record_reject(symbol, 'GLOBAL_TREND', reject_reason)
                elif "STRUCTURE" in reject_reason:
                    diagnostic_tracker.record_pass(symbol, 'GLOBAL_TREND')
                    diagnostic_tracker.record_reject(symbol, 'MARKET_STRUCTURE', reject_reason)
                else:
                    diagnostic_tracker.record_pass(symbol, 'GLOBAL_TREND')
                    diagnostic_tracker.record_pass(symbol, 'MARKET_STRUCTURE')
                    diagnostic_tracker.record_reject(symbol, 'ENTRY_GATE', reject_reason)

                with stats_lock:
                    entry_funnel['ENTRY_GATE_FAIL'] += 1
                    if "GLOBAL_TREND" in reject_reason:
                        entry_funnel['GLOBAL_TREND_FAIL'] += 1
                        entry_stats['REJECT_BAD_GLOBAL_TREND'] += 1
                    elif "STRUCTURE" in reject_reason:
                        entry_funnel['STRUCTURE_FAIL'] += 1
                        entry_stats['REJECT_BAD_STRUCTURE'] += 1
                    elif "CONFIRMATION" in reject_reason:
                        entry_funnel['CONFIRMATION_FAIL'] += 1
                        entry_stats['REJECT_NO_CONFIRMATION'] += 1
                    elif "BROKEN_LEVEL" in reject_reason:
                        entry_stats['REJECT_NO_BROKEN_LEVEL'] += 1
                    elif "CANDLE" in reject_reason:
                        entry_stats['REJECT_CANDLE_CLOSE'] += 1
                    elif "SWEEP" in reject_reason:
                        entry_stats['REJECT_NO_REAL_SWEEP'] += 1
                    elif "SCORE" in reject_reason:
                        entry_stats['REJECT_LOW_SCORE'] += 1
                    elif "CLOSE" in reject_reason:
                        entry_stats['REJECT_SR_TOO_CLOSE'] += 1
                    elif "RSI" in reject_reason:
                        entry_stats['REJECT_RSI_EXTREME'] += 1
                    elif "NOT_IN_RANGE" in reject_reason:
                        entry_stats['REJECT_NOT_IN_RANGE'] += 1
                    else:
                        entry_stats['REJECT_UNKNOWN_SETUP'] += 1
                
                record_entry_result(eng_setup, direction_str, False, reject_reason)
            
            if LOG_ENTRY_GATE and do_log:
                logger.info(f"[X] {symbol} - 1-й слой: НЕТ ({reject_reason})")
            return False, reject_reason
            
        if is_live:
            diagnostic_tracker.record_pass(symbol, 'GLOBAL_TREND')
            diagnostic_tracker.record_pass(symbol, 'MARKET_STRUCTURE')
            diagnostic_tracker.record_pass(symbol, 'ENTRY_GATE')
            with stats_lock:
                entry_stats['ENTRY_GATE_PASS'] += 1
                entry_funnel['ENTRY_GATE_PASS'] += 1
                
            record_entry_result(eng_setup, direction_str, True)
                
        # Успешный проход 1-го слоя будет залогирован в main.py
        return True, "PASS"


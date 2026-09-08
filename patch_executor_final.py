import sys

def patch_executor():
    with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '_log_risk_reject' not in content:
        helper = '''
    def _log_risk_reject(self, symbol, direction, setup_type, entry, atr, sl, tp, risk_usdt, current_price, actual_leverage, reject_reason, risk_distance=None):
        if risk_distance is None and sl:
            risk_distance = abs(entry - sl)
        elif risk_distance is None:
            risk_distance = 0.0
            
        sl_atr = risk_distance / atr if atr else 0.0
        sl_pct = (risk_distance / current_price) * 100 if current_price else 0.0
        
        # Calculate theoretical size
        position_size = risk_usdt / risk_distance if risk_distance > 0 else 0.0
        notional = position_size * current_price
        margin = notional / actual_leverage if actual_leverage else 0.0
        
        rr = 0.0
        if sl and tp and risk_distance > 0:
            reward = abs(tp - entry)
            rr = reward / risk_distance
            
        try:
            from config import MAX_SL_ATR
        except ImportError:
            MAX_SL_ATR = 3.0
            
        log_msg = (
            f"\\nRISK DIAGNOSTIC LOG (REJECTED)\\n"
            f"{symbol} {direction}\\n"
            f"Setup: {setup_type}\\n"
            f"Entry: {entry:.4f}\\n"
            f"ATR: {atr:.4f}\\n"
            f"SL: {sl if sl else 0.0:.4f} (Distance: {risk_distance:.4f})\\n"
            f"SL/ATR: {sl_atr:.2f}\\n"
            f"SL %: {sl_pct:.2f}%\\n"
            f"TP: {tp if tp else 0.0:.4f}\\n"
            f"RR: {rr:.2f}\\n"
            f"Risk USDT: {risk_usdt:.2f}\\n"
            f"Theoretical Position Size: {position_size}\\n"
            f"Theoretical Notional: {notional:.2f} USDT\\n"
            f"Theoretical Margin: {margin:.2f} USDT\\n"
            f"MAX_SL_ATR config: {MAX_SL_ATR}\\n"
            f"Reject Reason: {reject_reason}\\n"
        )
        self.logger.warning(log_msg)
'''
        content = content.replace('    def update_real_balance(self, balance: float):', helper + '\n    def update_real_balance(self, balance: float):')
        
    with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
        f.write(content)

patch_executor()

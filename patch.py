import json
with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_keys = """            self.positions[symbol] = {
                'side': side,
                'entry_price': actual_position_amount['average'] if actual_position_amount and 'average' in actual_position_amount else current_price,
                'amount': amount_coin,
                'margin_required': margin_required,
                'sl_id': sl_order['id'] if sl_order else None,
                'tp_id': tp_order['id'] if tp_order else None,
                'sl_price': sl_price,
                'tp_price': tp_price,
                'setup_type': setup_type,
                'engine_context': engine_context,
                'atr_value': atr_value
            }"""

new_keys = """            entry_p = actual_position_amount['average'] if actual_position_amount and 'average' in actual_position_amount else current_price
            self.positions[symbol] = {
                'side': side,
                'entry': float(entry_p),
                'max_price': float(entry_p),
                'min_price': float(entry_p),
                'amount': float(amount_coin),
                'margin_required': margin_required,
                'sl_order_id': sl_order['id'] if sl_order else None,
                'tp_order_id': tp_order['id'] if tp_order else None,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'setup_type': setup_type,
                'engine_context': engine_context,
                'atr_value': atr_value
            }"""

source = source.replace(old_keys, new_keys)

# Also fix PnL logic in fetch_my_trades
old_pnl = """                        recent_closes = [t for t in closed_trades if t['side'] == close_side and t['timestamp'] > (time.time() - 86400) * 1000]"""

new_pnl = """                        # Fix: Ensure we only consider trades closed AFTER our entry timestamp, or if missing, just a very recent window
                        entry_ts = pos_data.get('timestamp', time.time() * 1000 - 60000)
                        recent_closes = [t for t in closed_trades if t['side'] == close_side and t['timestamp'] >= entry_ts]
                        
                        # Fallback if the trade isn't indexed yet: Calculate approximate PnL based on Mark Price / Stop Price
                        # The actual realizedPnl will be recorded in Binance history, but for Telegram notifications, 
                        # an approximate PnL is better than an old incorrect trade."""

source = source.replace(old_pnl, new_pnl)

# Also add timestamp to execute_trade
old_exec_ts = """                'engine_context': engine_context,"""
new_exec_ts = """                'engine_context': engine_context,
                'timestamp': time.time() * 1000,"""
source = source.replace(old_exec_ts, new_exec_ts)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

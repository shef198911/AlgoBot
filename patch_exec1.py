import re

with open('executor.py', 'r', encoding='utf-8') as f:
    exec_source = f.read()

# 1. Rename amount_usdt to risk_usdt
exec_source = exec_source.replace('def execute_trade(self, symbol, side, amount_usdt, current_price', 'def execute_trade(self, symbol, side, risk_usdt, current_price')
exec_source = exec_source.replace('amount_usdt', 'risk_usdt')

# 2. Fix actual_position_amount vs actual_price
old_fetch = r"""            actual_price = order\.get\('average'\) or order\.get\('price'\)\n            actual_position_amount = float\(order\.get\('filled'\) or order\.get\('amount'\) or amount_coin\)"""
new_fetch = """            actual_price = order.get('average') or order.get('price')
            actual_position_amount = float(order.get('filled') or order.get('amount') or amount_coin)"""
exec_source = re.sub(old_fetch, new_fetch, exec_source)

# Fix the entry_p line
old_entry_p = r"entry_p = actual_position_amount\['average'\] if actual_position_amount and 'average' in actual_position_amount else current_price"
new_entry_p = "entry_p = actual_price if actual_price else current_price"
exec_source = re.sub(old_entry_p, new_entry_p, exec_source)

# Fix sl_order vs sl_ord
exec_source = exec_source.replace("'sl_order_id': sl_order['id'] if sl_order else None,", "'sl_order_id': sl_order_id,")
exec_source = exec_source.replace("'tp_order_id': tp_order['id'] if tp_order else None,", "'tp_order_id': tp_order_id,")

# Now handle the outer try-except emergency close. 
# We need to only emergency_close if the position is NOT protected!
# If sl_order_id is set, the position is protected.
# Wait, the outer try-except is:
outer_except = r"""            if position_opened:
                self\.logger\.critical\(f"КРИТИЧЕСКАЯ ОШИБКА: Сбой после открытия.*?"\)
                close_side = 'sell' if side == 'buy' else 'buy'
                close_amount = actual_position_amount if actual_position_amount else amount_coin
                try:
                    self\.exchange\.create_market_order\(symbol, close_side, close_amount, params=\{'reduceOnly': True\}\)
                except Exception as close_e:
                    self\.logger\.critical\(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось экстренно.*?"\)
                self\.emergency_close\(symbol\)
                return False"""
# Oh wait, my phase3b script added `self.emergency_close(symbol)` right after `try...except close_e:` 
# I will use AST or simpler text replacement. Let's just look at the exact text in executor.py.
with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(exec_source)

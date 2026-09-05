import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_block = """            self.positions[symbol] = {
                "side": side,
                "entry": actual_price,
                "amount": actual_position_amount,
                "sl_order_id": sl_order_id,
                "sl_price": sl_price,
                "tp_order_id": tp_order_id,
                "tp_price": tp_price,
                "max_price": actual_price,
                "min_price": actual_price
            }"""

new_block = """            self.positions[symbol] = {
                "side": side,
                "entry": actual_price,
                "amount": actual_position_amount,
                "sl_order_id": sl_order_id,
                "sl_price": sl_price,
                "tp_order_id": tp_order_id,
                "tp_price": tp_price,
                "max_price": actual_price,
                "min_price": actual_price,
                "engine_context": engine_context,
                "setup_type": setup_type,
                "atr_value": atr_value
            }"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

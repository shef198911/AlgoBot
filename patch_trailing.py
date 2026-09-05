import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_block = """                    elif needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        is_valid_stop = (new_sl_price < current_price) if is_long else (new_sl_price > current_price)"""

new_block = """                    elif needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        if new_sl_price == pos_data['sl_price']:
                            needs_trailing_update = False
                            
                    if needs_trailing_update:
                        is_valid_stop = (new_sl_price < current_price) if is_long else (new_sl_price > current_price)"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

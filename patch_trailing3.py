import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

# We need to replace the entire block starting from elif needs_trailing_update:
# Down to the end of the if USE_TRAILING: block
# Since we just want to avoid the spam, let's just insert a check:

old_str = """                            elif calculated_sl > pos_data['sl_price']:
                                new_sl_price = calculated_sl
                                needs_trailing_update = True"""

new_str = """                            elif calculated_sl > pos_data['sl_price']:
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if formatted_sl > pos_data['sl_price']:
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True"""

source = source.replace(old_str, new_str)

old_str_short = """                            elif calculated_sl < pos_data['sl_price'] or pos_data['sl_price'] == 0:
                                new_sl_price = calculated_sl
                                needs_trailing_update = True"""

new_str_short = """                            elif calculated_sl < pos_data['sl_price'] or pos_data['sl_price'] == 0:
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if pos_data['sl_price'] == 0 or formatted_sl < pos_data['sl_price']:
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True"""

source = source.replace(old_str_short, new_str_short)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

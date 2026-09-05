import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

bad_block = """                    elif needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        if new_sl_price == pos_data['sl_price']:
                            needs_trailing_update = False
                            
                    if needs_trailing_update:
                        is_valid_stop = (new_sl_price < current_price) if is_long else (new_sl_price > current_price)"""

good_block = """                    elif needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        if new_sl_price == pos_data['sl_price']:
                            needs_trailing_update = False
                            
                        if needs_trailing_update:
                            is_valid_stop = (new_sl_price < current_price) if is_long else (new_sl_price > current_price)"""

source = source.replace(bad_block, good_block)

# Indent everything that follows "if needs_trailing_update:"
lines = source.split('\n')
in_trailing_block = False
new_lines = []
for line in lines:
    if line.startswith('                        if needs_trailing_update:'):
        in_trailing_block = True
        new_lines.append(line)
        continue
    
    if in_trailing_block:
        if line.startswith('                        if not is_valid_stop:'):
            new_lines.append('    ' + line)
        elif line.startswith('                            self.logger.info(f"⚡ Цена'):
            new_lines.append('    ' + line)
        elif line.startswith('                            try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                self.exchange.cancel_all_orders(symbol)'):
            new_lines.append('    ' + line)
        elif line.startswith('                            except:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                pass'):
            new_lines.append('    ' + line)
        elif line.startswith('                            try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                self.exchange.create_market_order'):
            new_lines.append('    ' + line)
        elif line.startswith('                            except Exception as ce:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                self.logger.error'):
            new_lines.append('    ' + line)
        elif line.startswith('                        else:'):
            new_lines.append('    ' + line)
        elif line.startswith('                            try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                # Ставим новый стоп'):
            new_lines.append('    ' + line)
        elif line.startswith('                                sl_ord = self.exchange'):
            new_lines.append('    ' + line)
        elif line.startswith('                                # Если успешно, отменяем старый стоп'):
            new_lines.append('    ' + line)
        elif line.startswith('                                old_sl = pos_data'):
            new_lines.append('    ' + line)
        elif line.startswith('                                if old_sl:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        self.exchange.cancel_order'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    except:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        pass'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        '):
            new_lines.append('    ' + line)
        elif line.startswith('                                pos_data[\'sl_order_id\']'):
            new_lines.append('    ' + line)
        elif line.startswith('                                pos_data[\'sl_price\']'):
            new_lines.append('    ' + line)
        elif line.startswith('                                self._save_live_state()'):
            new_lines.append('    ' + line)
        elif line.startswith('                                self.logger.info'):
            new_lines.append('    ' + line)
        elif line.startswith('                                tg_notifier.send_message'):
            new_lines.append('    ' + line)
        elif line.startswith('                            except Exception as e:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                err_str = str(e)'):
            new_lines.append('    ' + line)
        elif line.startswith('                                if "-2021" in err_str'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    self.logger.info'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        self.exchange.cancel_all_orders'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    except:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        pass'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    try:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        self.exchange.create_market_order'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    except Exception as ce2:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                        self.logger.error'):
            new_lines.append('    ' + line)
        elif line.startswith('                                else:'):
            new_lines.append('    ' + line)
        elif line.startswith('                                    self.logger.error'):
            new_lines.append('    ' + line)
        elif line.startswith('                # End of positions loop'):
            # Stop indenting
            in_trailing_block = False
            new_lines.append(line)
        else:
            # If we hit an empty line or something, we probably should keep indenting
            if line.strip() == '':
                new_lines.append(line)
            else:
                # Stop indenting if it's back to outer scope
                if not line.startswith('                        '):
                    in_trailing_block = False
                    new_lines.append(line)
                else:
                    new_lines.append('    ' + line)
    else:
        new_lines.append(line)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

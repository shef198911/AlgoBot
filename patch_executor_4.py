import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_block = """            try:
                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'reduceOnly': True})
                sl_order_id = sl_ord['id']
            except Exception as e:
                self.logger.error(f"Не удалось выставить SL: {e}. Экстренное закрытие позиции!")
                try:
                    self.exchange.create_market_order(symbol, close_side, amount_coin, params={'reduceOnly': True})
                except Exception as close_e:
                    self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")
                return False"""

new_block = """            try:
                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'reduceOnly': True})
                sl_order_id = sl_ord['id']
            except Exception as e:
                self.logger.error(f"Сбой установки SL: {e}. Пробуем повторить...")
                import time
                time.sleep(1)
                try:
                    sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'reduceOnly': True})
                    sl_order_id = sl_ord['id']
                except Exception as e2:
                    self.logger.error(f"Повторный сбой SL: {e2}. Экстренное закрытие позиции!")
                    close_amount = actual_position_amount if actual_position_amount else amount_coin
                    try:
                        self.exchange.create_market_order(symbol, close_side, close_amount, params={'reduceOnly': True})
                    except Exception as close_e:
                        self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")
                    return False"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

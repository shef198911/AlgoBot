import sys
import re

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Fix 1: check_position_status
source = source.replace(
    'self.logger.warning(f"Попытка открыть сделку по {symbol}, но мы уже в позиции!")\n            return False',
    'err = f"Попытка открыть сделку по {symbol}, но мы уже в позиции!"\n            self.logger.warning(err)\n            self.last_error = err\n            return False'
)

# Fix 2: MAX_CAPITAL_USDT
source = source.replace(
    'self.logger.warning(f"Достигнут лимит капитала! Выделено {MAX_CAPITAL_USDT} USDT, уже используется {current_used_capital} USDT. Пропускаем {symbol}.")\n            return False',
    'err = f"Достигнут лимит капитала! Выделено {MAX_CAPITAL_USDT} USDT, уже используется {current_used_capital} USDT. Пропускаем {symbol}."\n            self.logger.warning(err)\n            self.last_error = err\n            return False'
)

# Fix 3: Risk Engine
source = source.replace(
    'self.logger.warning(f"Сделка {symbol} отклонена Risk Engine: {trade_plan.get(\'reason\')}")\n                    return False',
    'err = f"Сделка {symbol} отклонена Risk Engine: {trade_plan.get(\'reason\')}"\n                    self.logger.warning(err)\n                    self.last_error = err\n                    return False'
)

# Fix 4: amount_coin <= 0
source = source.replace(
    'if amount_coin <= 0:\n                return False',
    'if amount_coin <= 0:\n                self.last_error = "Рассчитанный объем позиции (amount_coin) <= 0"\n                return False'
)

# Fix 5: SL retry failure
source = source.replace(
    'self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")\n                    return False',
    'self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")\n                    self.last_error = f"Сбой установки SL и сбой экстренного закрытия: {close_e}"\n                    return False'
)

source = source.replace(
    'self.logger.error(f"Повторный сбой SL: {e2}. Экстренное закрытие позиции!")\n                    close_amount = actual_position_amount if actual_position_amount else amount_coin\n                    try:\n                        self.exchange.create_market_order(symbol, close_side, close_amount, params={\'reduceOnly\': True})\n                    except Exception as close_e:\n                        self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")\n                        self.last_error = f"Сбой установки SL и сбой экстренного закрытия: {close_e}"\n                        return False',
    'self.logger.error(f"Повторный сбой SL: {e2}. Экстренное закрытие позиции!")\n                    self.last_error = f"Сбой установки SL: {e2}. Сработало экстренное закрытие позиции!"\n                    close_amount = actual_position_amount if actual_position_amount else amount_coin\n                    try:\n                        self.exchange.create_market_order(symbol, close_side, close_amount, params={\'reduceOnly\': True})\n                    except Exception as close_e:\n                        self.logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось закрыть позицию после сбоя SL: {close_e}")\n                        self.last_error = f"Сбой установки SL и сбой экстренного закрытия: {close_e}"\n                    return False'
)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

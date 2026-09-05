import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

# We need to remove the old capital check at line 31
old_check = '''        current_used_capital = len(self.positions) * amount_usdt
        if current_used_capital + amount_usdt > MAX_CAPITAL_USDT:
            err = f"Максимальный капитал исчерпан! Лимит {MAX_CAPITAL_USDT} USDT, используется {current_used_capital} USDT. Пропуск {symbol}."
            self.logger.warning(err)
            self.last_error = err
            return False'''
# I need to match it roughly, maybe it has Russian chars or weird encodings

import sys
import re

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = re.sub(r'        current_used_capital = len\(self\.positions\) \* amount_usdt\n        if current_used_capital \+ amount_usdt > MAX_CAPITAL_USDT:\n            err = f".*?"\n            self\.logger\.warning\(err\)\n            self\.last_error = err\n            return False\n', '', source, flags=re.DOTALL)

replacement = '''                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                margin_required = (amount_coin * current_price) / LEVERAGE

            # Check Margin Capital Limit
            current_total_margin = sum(pos.get('margin_required', 0) for pos in self.positions.values())
            if current_total_margin + margin_required > MAX_CAPITAL_USDT:
                err = f"Максимальный капитал исчерпан! Лимит {MAX_CAPITAL_USDT} USDT, используется {current_total_margin:.2f} + требуется {margin_required:.2f}. Пропуск {symbol}."
                self.logger.warning(err)
                self.last_error = err
                return False
                
            # Recalculate actual risk after precision rounding
            if trade_plan and trade_plan.get('valid'):
                actual_risk = amount_coin * trade_plan['risk_distance']
                self.logger.info(f"Actual Risk after rounding: {actual_risk:.2f}$ (Target Risk: {amount_usdt:.2f}$)")
                if actual_risk > amount_usdt * 1.1: # 10% tolerance for rounding up on small sizes
                    err = f"Risk {actual_risk:.2f}$ exceeds target {amount_usdt}$ after precision rounding! Skip."
                    self.logger.warning(err)
                    self.last_error = err
                    return False

            order = self.exchange.create_order('''

source = source.replace('''                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))

            order = self.exchange.create_order(''', replacement)


context_insert = '''            self.positions[symbol] = {
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
            }'''

source = re.sub(r'            self\.positions\[symbol\] = \{.*?\n            \}', context_insert, source, flags=re.DOTALL)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

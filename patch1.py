import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

redundant_block = """            # Рассчитываем SL/TP до отправки запроса
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                recalc_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if recalc_plan.get('valid'):
                    sl_price = recalc_plan['stop_loss']
                    tp_price = recalc_plan['take_profit']
                elif self.last_trade_plan:
                    sl_price = self.last_trade_plan['stop_loss']
                    tp_price = self.last_trade_plan['take_profit']
            # else: sl_price, tp_price already set above from calculate_sl_tp"""

if redundant_block in code:
    code = code.replace(redundant_block, "")
    print('Redundant block removed.')

code = code.replace("'risk_usdt': risk_usdt,", "'risk_usdt': risk_usdt_actual,")

code = code.replace("self.positions[symbol] = {\n                    'side': side,", "self.positions[symbol] = {\n                    'entry_order_id': order.get('id'),\n                    'side': side,")
code = code.replace("self.positions[symbol] = {\n                            'side': actual_side,", "self.positions[symbol] = {\n                            'entry_order_id': order.get('id'),\n                            'side': actual_side,")

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched executor.py part 1')

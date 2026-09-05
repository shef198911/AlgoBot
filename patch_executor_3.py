import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_block = """            sl_price, tp_price = self.calculate_sl_tp(side, actual_price, atr_value, dynamic_tp=dynamic_tp)
            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))"""

new_block = """            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                direction_str = 'LONG' if side == 'buy' else 'SHORT'
                # Recalculate based on actual fill price
                recalc_plan = self.risk_engine.build_trade_plan(direction_str, actual_price, setup_type, engine_context, atr_value)
                if recalc_plan.get('valid'):
                    sl_price = recalc_plan['stop_loss']
                    tp_price = recalc_plan['take_profit']
                else:
                    # If actual fill makes RR invalid, we might want to just close it immediately or use fallback!
                    # For safety, let's use the stop loss from the planned entry if it was valid, or recalculate anyway.
                    # Wait, SL is structural, so the price level stays the same!
                    sl_price = self.last_trade_plan['stop_loss']
                    tp_price = self.last_trade_plan['take_profit']
            else:
                sl_price, tp_price = self.calculate_sl_tp(side, actual_price, atr_value, dynamic_tp=dynamic_tp)
                
            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

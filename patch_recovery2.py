import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                        if pos_data.get('sl_price') and not pos_data.get('sl_order_id'):
                            try:
                                close_side = 'sell' if pos_data['side'] in ['buy', 'long'] else 'buy'
                                sl_order = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, exchange_amt, params={'stopPrice': pos_data['sl_price'], 'reduceOnly': True})
                                pos_data['sl_order_id'] = sl_order.get('id')
                            except Exception:
                                pass
                                
                        if pos_data.get('tp_price') and not pos_data.get('tp_order_id'):
                            try:
                                close_side = 'sell' if pos_data['side'] in ['buy', 'long'] else 'buy'
                                tp_order = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, exchange_amt, params={'stopPrice': pos_data['tp_price'], 'reduceOnly': True})
                                pos_data['tp_order_id'] = tp_order.get('id')
                            except Exception:
                                pass"""

replacement = """                        if not pos_data.get('sl_order_id') or not pos_data.get('tp_order_id'):
                            close_side = 'sell' if pos_data['side'] in ['buy', 'long'] else 'buy'
                            cur_entry = pos_data.get('entry', current_price)
                            atr_val = pos_data.get('atr_value', 0.0)
                            ctx = pos_data.get('engine_context')
                            setup_type = pos_data.get('setup_type')
                            dir_str = 'LONG' if pos_data['side'] in ['buy', 'long'] else 'SHORT'

                            sl_p = pos_data.get('sl_price')
                            tp_p = pos_data.get('tp_price')

                            if not sl_p or not tp_p:
                                if STRUCTURE_RISK_ENABLED and ctx and setup_type:
                                    plan = self.risk_engine.build_trade_plan(dir_str, cur_entry, setup_type, ctx, atr_val)
                                    if plan.get('valid'):
                                        sl_p = plan['stop_loss']
                                        tp_p = plan['take_profit']
                                    else:
                                        sl_p, tp_p = self.calculate_sl_tp(pos_data['side'], cur_entry, atr_val)
                                else:
                                    sl_p, tp_p = self.calculate_sl_tp(pos_data['side'], cur_entry, atr_val)

                            try:
                                p = self.exchange.price_to_precision(symbol, sl_p)
                                sl_p = float(p) if p else float(sl_p)
                            except Exception:
                                sl_p = float(sl_p) if sl_p else 0.0
                            try:
                                p = self.exchange.price_to_precision(symbol, tp_p)
                                tp_p = float(p) if p else float(tp_p)
                            except Exception:
                                tp_p = float(tp_p) if tp_p else 0.0

                            if not pos_data.get('sl_order_id'):
                                try:
                                    sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, exchange_amt, params={'stopPrice': sl_p, 'reduceOnly': True})
                                    pos_data['sl_order_id'] = sl_ord.get('id')
                                    pos_data['sl_price'] = sl_p
                                except Exception as e:
                                    self.emergency_close(symbol, fallback_amount=exchange_amt, side=pos_data['side'])

                            if pos_data.get('sl_order_id') and not pos_data.get('tp_order_id'):
                                pos_data['tp_retries'] = pos_data.get('tp_retries', 0) + 1
                                if pos_data['tp_retries'] <= 5:
                                    try:
                                        tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, exchange_amt, params={'stopPrice': tp_p, 'reduceOnly': True})
                                        pos_data['tp_order_id'] = tp_ord.get('id')
                                        pos_data['tp_price'] = tp_p
                                    except Exception:
                                        pass"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated recovery logic in check_position_status")

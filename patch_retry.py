import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                        if USE_TRAILING and pos_data.get('max_price') and pos_data.get('sl_price') and pos_data.get('sl_order_id'):"""

replacement = """                        if pos_data.get('sl_price') and not pos_data.get('sl_order_id'):
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
                                pass

                        if USE_TRAILING and pos_data.get('max_price') and pos_data.get('sl_price') and pos_data.get('sl_order_id'):"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added SL/TP retry to check_position_status")

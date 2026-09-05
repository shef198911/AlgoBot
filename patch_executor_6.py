import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_block = """                if self.positions[symbol]['sl_order_id'] is None:

                
                    self.logger.critical(f"КРИТИЧЕСКИ: Позиция {symbol} найдена, но защитный SL не установлен или не найден! ПОТРЕБУЕТСЯ РУЧНОЕ ВМЕШАТЕЛЬСТВО!")"""

new_block = """                if self.positions[symbol]['sl_order_id'] is None:
                    self.logger.critical(f"КРИТИЧЕСКИ: Позиция {symbol} найдена, но защитный SL не найден. Пробуем восстановить...")
                    
                    # 1. Get real pos and entry
                    entry_price = self.positions[symbol]['entry']
                    side = self.positions[symbol]['side']
                    direction_str = 'LONG' if side in ['buy', 'long'] else 'SHORT'
                    
                    # 2. Get context
                    ctx = self.positions[symbol].get('engine_context')
                    setup_type = self.positions[symbol].get('setup_type')
                    atr_value = self.positions[symbol].get('atr_value', 0.0)
                    amount_coin = self.positions[symbol]['amount']
                    close_side = 'sell' if direction_str == 'LONG' else 'buy'
                    
                    sl_price, tp_price = 0, 0
                    if STRUCTURE_RISK_ENABLED and ctx and setup_type:
                        plan = self.risk_engine.build_trade_plan(direction_str, entry_price, setup_type, ctx, atr_value)
                        if plan.get('valid'):
                            sl_price = plan['stop_loss']
                            tp_price = plan['take_profit']
                            self.logger.info(f"Восстановлен structural SL/TP: {sl_price} / {tp_price}")
                        else:
                            sl_price, tp_price = self.calculate_sl_tp(side, entry_price, atr_value)
                            self.logger.warning(f"Structural SL/TP invalid. Fallback emergency: {sl_price} / {tp_price}")
                    else:
                        sl_price, tp_price = self.calculate_sl_tp(side, entry_price, atr_value)
                        self.logger.warning(f"Нет контекста структуры. Fallback emergency SL/TP: {sl_price} / {tp_price}")
                        
                    sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
                    tp_price = float(self.exchange.price_to_precision(symbol, tp_price))
                    
                    try:
                        sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'reduceOnly': True})
                        self.positions[symbol]['sl_order_id'] = sl_ord['id']
                        self.positions[symbol]['sl_price'] = sl_price
                    except Exception as e:
                        self.logger.critical(f"Не удалось восстановить SL: {e}")
                        
                    try:
                        tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, amount_coin, params={'stopPrice': tp_price, 'reduceOnly': True})
                        self.positions[symbol]['tp_order_id'] = tp_ord['id']
                        self.positions[symbol]['tp_price'] = tp_price
                    except Exception as e:
                        self.logger.critical(f"Не удалось восстановить TP: {e}")
                        
                    self._save_live_state()"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

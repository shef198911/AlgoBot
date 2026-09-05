import time
import json
from risk_manager import StructureRiskEngine
from config import STRUCTURE_RISK_ENABLED
import pandas as pd
from config import logger, STOP_LOSS_PCT, TAKE_PROFIT_PCT, LEVERAGE, MAX_CAPITAL_USDT, USE_ATR, USE_TRAILING, TRAILING_ACTIVATION_PCT, TRAILING_DISTANCE_PCT
from analytics import analytics_manager
from telegram_notifier import TelegramNotifier

tg_notifier = TelegramNotifier()

class TraderExecutor:
    def __init__(self, exchange_client):
        self.logger = logger.getChild("TraderExecutor")
        self.risk_engine = StructureRiskEngine()
        self.exchange = exchange_client
        self.positions = {} # Стейт-менеджмент позиций {symbol: {"side": side, "entry": price, "max_profit": 0, "sl_order_id": id, "amount_coin": amount}}
        self.pending_margins = {}
        import threading
        self.state_lock = threading.Lock()
        self.capital_lock = threading.Lock()
        self.last_error = ""
        
        try:
            self.exchange.load_markets()
        except:
            pass

    def execute_trade(self, symbol, side, risk_usdt, current_price, atr_value=0.0, dynamic_tp=None, setup_type=None, engine_context=None):
        if self.check_position_status(symbol):
            err = f"Попытка открыть сделку по {symbol}, но мы уже в позиции!"
            self.logger.warning(err)
            self.last_error = err
            return False
            
        # Margins will be calculated below

        position_opened = False
        actual_position_amount = None
        sl_order_id = None
        try:
            if symbol not in self.exchange.markets:
                self.exchange.load_markets()
                
            try:
                self.exchange.set_leverage(LEVERAGE, symbol)
            except Exception as e:
                pass
                
            direction_str = 'LONG' if side == 'buy' else 'SHORT'
            trade_plan = None
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                trade_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if not trade_plan.get('valid'):
                    err = f"Сделка {symbol} отклонена Risk Engine: {trade_plan.get('reason')}"
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                
                # risk_usdt is the risk we are willing to take (how much to lose)
                risk_distance = trade_plan['risk_distance']
                amount_coin = risk_usdt / risk_distance
                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                
                # Check worst-case risk after precision rounding
                worst_case_risk = amount_coin * risk_distance
                if worst_case_risk > risk_usdt * 1.05:
                    err = f"Worst-case risk {worst_case_risk:.2f} exceeds limit {risk_usdt:.2f} by >5% after precision rounding."
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                    
                volume_usdt = amount_coin * current_price
                margin_required = volume_usdt / LEVERAGE
                self.logger.info(f"Structure Risk: SL distance {risk_distance:.4f}. Position size {amount_coin} {symbol} (Vol: {volume_usdt:.2f}$, Margin: {margin_required:.2f}$)")
            else:
                # Fallback to old logic
                volume_usdt = risk_usdt * LEVERAGE
                amount_coin = volume_usdt / current_price
                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                margin_required = volume_usdt / LEVERAGE
            
            if amount_coin <= 0:
                self.last_error = "Рассчитанный объем позиции (amount_coin) <= 0"
                return False

            with self.capital_lock:
                current_total_margin = sum(pos.get('margin_required', 0.0) for pos in self.positions.values()) + sum(self.pending_margins.values())
                if current_total_margin + margin_required > MAX_CAPITAL_USDT:
                    err = f"Лимит капитала исчерпан! Макс: {MAX_CAPITAL_USDT} USDT, исп: {current_total_margin:.2f} USDT (с ожидаемыми). Пропуск {symbol}."
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                self.pending_margins[symbol] = margin_required

            self.logger.info(f"Подготовка {side.upper()} ордера: {amount_coin} {symbol} (Lev: {LEVERAGE}x)")

            # Save plan to use it for protective orders
            self.last_trade_plan = trade_plan
            self.last_engine_context = engine_context

            # Рассчитываем SL/TP до отправки запроса
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                direction_str = 'LONG' if side == 'buy' else 'SHORT'
                recalc_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if recalc_plan.get('valid'):
                    sl_price = recalc_plan['stop_loss']
                    tp_price = recalc_plan['take_profit']
                else:
                    sl_price = self.last_trade_plan['stop_loss']
                    tp_price = self.last_trade_plan['take_profit']
            else:
                sl_price, tp_price = self.calculate_sl_tp(side, current_price, atr_value, dynamic_tp=dynamic_tp)

            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))
            close_side = 'sell' if side == 'buy' else 'buy'

            self.logger.info(f"Выставляем рыночный ордер: {amount_coin} {symbol}...")
            order = self.exchange.create_market_order(symbol, side, amount_coin)
            
            position_opened = True
            self.logger.info(f"✅ Базовый ордер исполнен! ID: {order['id']}")

            actual_price = order.get('average') or order.get('price') or current_price
            actual_position_amount = float(order.get('filled') or order.get('amount') or 0.0)
            
            if actual_position_amount <= 0:
                try:
                    positions = self.exchange.fetch_positions([symbol]) if hasattr(self.exchange, 'has') and self.exchange.has.get('fetchPositions') else self.exchange.fetch_positions()
                    for pos in positions:
                        pos_sym = pos.get('symbol', '')
                        if pos_sym.split(':')[0] == symbol.split(':')[0]:
                            actual_position_amount = abs(float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0))))
                            break
                except Exception as pos_e:
                    self.logger.error(f"Не удалось получить фактический объем позиции для {symbol}: {pos_e}")
            
            if actual_position_amount <= 0:
                self.logger.critical(f"Не удалось подтвердить объем открытой позиции для {symbol}. Сохраняем в стейт и вызываем emergency_close.")
                self.last_error = "UNKNOWN_AMOUNT"
                self.positions[symbol] = {
                    'side': side,
                    'entry': float(actual_price),
                    'max_price': float(actual_price),
                    'min_price': float(actual_price),
                    'amount': float(amount_coin),
                    'margin_required': margin_required,
                    'sl_order_id': None,
                    'tp_order_id': None,
                    'sl_price': float(sl_price),
                    'tp_price': float(tp_price),
                    'setup_type': setup_type,
                    'engine_context': engine_context,
                    'timestamp': time.time() * 1000,
                    'atr_value': atr_value,
                    'risk_usdt': risk_usdt,
                    'position_notional': volume_usdt,
                    'leverage': LEVERAGE
                }
                self._save_live_state()
                self.emergency_close(symbol)
                return False

            sl_order_id = None
            tp_order_id = None
            
            try:
                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, actual_position_amount, params={'stopPrice': sl_price, 'reduceOnly': True})
                sl_order_id = sl_ord['id']
            except Exception as sl_e:
                self.logger.error(f"⚠️ Ошибка при выставлении SL для {symbol}: {sl_e}")

            try:
                tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, actual_position_amount, params={'stopPrice': tp_price, 'reduceOnly': True})
                tp_order_id = tp_ord['id']
            except Exception as tp_e:
                self.logger.error(f"⚠️ Ошибка при выставлении TP для {symbol}: {tp_e}")

            if not sl_order_id:
                self.logger.critical(f"КРИТИЧЕСКИ: Позиция {symbol} открыта без SL. Выполняем экстренное закрытие.")
                self.emergency_close(symbol)
                return False
                
            entry_p = actual_price if actual_price else current_price
            self.positions[symbol] = {
                'side': side,
                'entry': float(entry_p),
                'max_price': float(entry_p),
                'min_price': float(entry_p),
                'amount': float(actual_position_amount) if actual_position_amount else float(amount_coin),
                'margin_required': margin_required,
                'sl_order_id': sl_order_id,
                'tp_order_id': tp_order_id,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'setup_type': setup_type,
                'engine_context': engine_context,
                'timestamp': time.time() * 1000,
                'atr_value': atr_value,
                'risk_usdt': risk_usdt,
                'position_notional': volume_usdt,
                'leverage': LEVERAGE
            }
            
            self._save_live_state()

            self.logger.info(f"Сделка {side} по {symbol} открыта. Вход: {current_price}, SL: {sl_price}, TP: {tp_price}")
            return True
        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Ошибка при выполнении execute_trade: {e}")
            if "-1021" in str(e) or "ahead of the server's time" in str(e):
                try:
                    self.exchange.load_time_difference()
                    self.logger.info("Выполнена авто-пересинхронизация времени с сервером Binance.")
                except:
                    pass
            if position_opened and not sl_order_id:
                self.logger.critical(f"КРИТИЧЕСКИ: Ошибка ПОСЛЕ открытия позиции {symbol}. Экстренное закрытие!")
                self.emergency_close(symbol)
            return False
        finally:
            with self.capital_lock:
                if symbol in self.pending_margins:
                    del self.pending_margins[symbol]


    def _save_live_state(self):
        with self.state_lock:
            try:
                with open("live_state.json", "w", encoding="utf-8") as f:
                    json.dump(self.positions, f, indent=4)
            except Exception as e:
                self.logger.error(f"Ошибка сохранения live_state: {e}")

    def calculate_sl_tp(self, side, entry_price, atr_value, dynamic_tp=None):
        if USE_ATR and atr_value > 0:
            sl_dist = atr_value * 1.5
            tp_dist = (entry_price * dynamic_tp) if dynamic_tp else (atr_value * 3.0)
            if side == 'buy':
                return entry_price - sl_dist, entry_price + tp_dist
            else:
                return entry_price + sl_dist, entry_price - tp_dist
        else:
            tp_pct = dynamic_tp if dynamic_tp else TAKE_PROFIT_PCT
            if side == 'buy':
                return entry_price * (1 - STOP_LOSS_PCT), entry_price * (1 + tp_pct)
            else:
                return entry_price * (1 + STOP_LOSS_PCT), entry_price * (1 - tp_pct)

    def check_position_status(self, symbol):
        try:
            positions = self.exchange.fetch_positions()
            active_pos = None
            for pos in positions:
                pos_sym = pos.get('symbol', '')
                if pos_sym.split(':')[0] == symbol.split(':')[0]:
                    amt = float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0)))
                    if abs(amt) > 0:
                        active_pos = pos
                        break
            
            if active_pos:
                if symbol not in self.positions:
                    loaded_from_state = False
                    try:
                        import os, json
                        if os.path.exists("live_state.json"):
                            with open("live_state.json", "r", encoding="utf-8") as f:
                                saved_state = json.load(f)
                                if symbol in saved_state and saved_state[symbol].get('sl_order_id'):
                                    self.positions[symbol] = saved_state[symbol]
                                    loaded_from_state = True
                    except Exception:
                        pass
                    
                    if not loaded_from_state:
                        self.positions[symbol] = {"side": active_pos['side'].lower(), "entry": float(active_pos['entryPrice']), "max_price": float(active_pos['entryPrice']), "min_price": float(active_pos['entryPrice']), "sl_order_id": None, "sl_price": 0, "tp_order_id": None, "tp_price": 0, "amount": abs(float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0))))}
                        
                # Вне зависимости от state, сверяем открытые ордера (verification)
                try:
                    open_orders = self.exchange.fetch_open_orders(symbol)
                    found_sl = None
                    found_tp = None
                    
                    for o in open_orders:
                        o_type = o.get('type', '').lower()
                        info_type = o.get('info', {}).get('origType', '').lower()
                        
                        is_stop = 'stop' in o_type or 'stop' in info_type
                        is_take_profit = 'take_profit' in o_type or 'take_profit' in info_type
                        
                        if is_stop:
                            found_sl = o['id']
                            self.positions[symbol]['sl_price'] = float(o.get('stopPrice') or 0)
                        elif is_take_profit:
                            found_tp = o['id']
                            self.positions[symbol]['tp_price'] = float(o.get('stopPrice') or 0)
                            
                    # Если ордер был в state, но его нет на бирже, он будет перезаписан в None и восстановлен
                    if self.positions[symbol].get('sl_order_id') != found_sl:
                        self.logger.warning(f"Сброс SL order ID для {symbol}, не совпадает с биржей.")
                        self.positions[symbol]['sl_order_id'] = found_sl
                    if self.positions[symbol].get('tp_order_id') != found_tp:
                        self.logger.warning(f"Сброс TP order ID для {symbol}, не совпадает с биржей.")
                        self.positions[symbol]['tp_order_id'] = found_tp
                        
                except Exception as e:
                    self.logger.warning(f"Не удалось верифицировать SL/TP ордера: {e}")
                    
                if not self.positions[symbol].get('sl_order_id'):
                    try:
                        market_id = symbol.replace('/', '').split(':')[0]
                        algo_orders = self.exchange.fapiPrivateGetOpenAlgoOrders({'symbol': market_id})
                        for ao in algo_orders:
                            ao_type = ao.get('orderType', '').lower()
                            if 'stop' in ao_type and not self.positions[symbol].get('sl_order_id'):
                                self.positions[symbol]['sl_order_id'] = str(ao.get('algoId'))
                                self.positions[symbol]['sl_price'] = float(ao.get('triggerPrice') or 0)
                            elif 'take_profit' in ao_type and not self.positions[symbol].get('tp_order_id'):
                                self.positions[symbol]['tp_order_id'] = str(ao.get('algoId'))
                                self.positions[symbol]['tp_price'] = float(ao.get('triggerPrice') or 0)
                    except Exception:
                        pass

                if self.positions[symbol].get('sl_order_id') is None or self.positions[symbol].get('tp_order_id') is None:
                    self.logger.critical(f"КРИТИЧЕСКИ: Позиция {symbol} найдена, но защитные ордера (SL/TP) отсутствуют. Пробуем восстановить...")
                    
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
                    
                    if not self.positions[symbol].get('sl_order_id'):
                        try:
                            sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'reduceOnly': True})
                            self.positions[symbol]['sl_order_id'] = sl_ord['id']
                            self.positions[symbol]['sl_price'] = sl_price
                        except Exception as e:
                            self.logger.critical(f"Не удалось восстановить SL: {e}")
                            
                    if not self.positions[symbol].get('tp_order_id'):
                        try:
                            tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, amount_coin, params={'stopPrice': tp_price, 'reduceOnly': True})
                            self.positions[symbol]['tp_order_id'] = tp_ord['id']
                            self.positions[symbol]['tp_price'] = tp_price
                        except Exception as e:
                            self.logger.critical(f"Не удалось восстановить TP: {e}")
                            
                    self._save_live_state()

                
                # Трейлинг стоп логика
                if USE_TRAILING:
                    pos_data = self.positions[symbol]
                    current_price = float(active_pos.get('markPrice', 0)) or float(active_pos.get('entryPrice', 0))
                    entry = pos_data['entry']
                    side = pos_data['side'].lower()
                    is_long = side in ['buy', 'long']
                    actual_amt = abs(float(active_pos.get('info', {}).get('positionAmt', pos_data.get('amount', 0))))
                    close_side = 'sell' if is_long else 'buy'
                    
                    needs_trailing_update = False
                    close_market_now = False
                    new_sl_price = pos_data['sl_price']
                    
                    if is_long:
                        if current_price > pos_data['max_price']:
                            pos_data['max_price'] = current_price
                        profit_pct = (pos_data['max_price'] - entry) / entry
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['max_price'] * (1 - TRAILING_DISTANCE_PCT)
                            if current_price <= calculated_sl:
                                close_market_now = True
                            elif calculated_sl > pos_data['sl_price']:
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if formatted_sl > pos_data['sl_price']:
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True
                    else: # short
                        if current_price < pos_data['min_price']:
                            pos_data['min_price'] = current_price
                        profit_pct = (entry - pos_data['min_price']) / entry
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['min_price'] * (1 + TRAILING_DISTANCE_PCT)
                            if current_price >= calculated_sl:
                                close_market_now = True
                            elif calculated_sl < pos_data['sl_price'] or pos_data['sl_price'] == 0:
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if pos_data['sl_price'] == 0 or formatted_sl < pos_data['sl_price']:
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True
                                
                    if close_market_now:
                        self.logger.info(f"⚡ Трейлинг-стоп сработал для {symbol}! Текущая цена {current_price} пробила стоп {calculated_sl:.4f}. Закрытие по маркету...")
                        try:
                            self.exchange.cancel_all_orders(symbol)
                        except:
                            pass
                        try:
                            self.exchange.create_market_order(symbol, close_side, actual_amt, params={'reduceOnly': True})
                            self.logger.info(f"✅ Позиция {symbol} успешно закрыта по трейлингу по рыночной цене.")
                        except Exception as ce:
                            self.logger.error(f"Ошибка закрытия по маркету при трейлинге: {ce}")
                    elif needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        is_valid_stop = (new_sl_price < current_price) if is_long else (new_sl_price > current_price)
                        
                        if not is_valid_stop:
                            self.logger.info(f"⚡ Цена {current_price} уже пересекла новый стоп {new_sl_price} для {symbol}. Закрываем по маркету!")
                            try:
                                self.exchange.cancel_all_orders(symbol)
                            except:
                                pass
                            try:
                                self.exchange.create_market_order(symbol, close_side, actual_amt, params={'reduceOnly': True})
                            except Exception as ce:
                                self.logger.error(f"Ошибка закрытия по маркету: {ce}")
                        else:
                            try:
                                # Ставим новый стоп
                                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, actual_amt, params={'stopPrice': new_sl_price, 'reduceOnly': True})
                                # Если успешно, отменяем старый стоп
                                old_sl = pos_data.get('sl_order_id')
                                if old_sl:
                                    try:
                                        self.exchange.cancel_order(old_sl, symbol)
                                    except:
                                        pass
                                        
                                pos_data['sl_order_id'] = sl_ord['id']
                                pos_data['sl_price'] = new_sl_price
                                self._save_live_state()
                                self.logger.info(f"🔄 Трейлинг-стоп передвинут для {symbol}: {new_sl_price}")
                                tg_notifier.send_message(f"🔄 <b>Трейлинг-стоп сдвинут!</b>\nМонета: {symbol}\nНовый стоп: {new_sl_price}")
                            except Exception as e:
                                err_str = str(e)
                                if "-2021" in err_str or "Order would immediately trigger" in err_str:
                                    self.logger.warning(f"Стоп {new_sl_price} мгновенно сработал бы для {symbol} (цена {current_price}). Закрываем по маркету!")
                                    try:
                                        self.exchange.cancel_all_orders(symbol)
                                    except:
                                        pass
                                    try:
                                        self.exchange.create_market_order(symbol, close_side, actual_amt, params={'reduceOnly': True})
                                    except Exception as ce:
                                        self.logger.error(f"Ошибка закрытия по маркету: {ce}")
                                else:
                                    self.logger.error(f"Ошибка сдвига трейлинга: {e}")

                return True
            
            # Позиция закрыта
            if symbol in self.positions:
                pos_data = self.positions[symbol]
                self.logger.info(f"🔔 Сделка по {symbol} закрыта.")
                
                # Попробуем получить PnL
                try:
                    closed_trades = self.exchange.fetch_my_trades(symbol, limit=20)
                    # Фильтруем сделки, закрывающие позицию
                    close_side = 'sell' if pos_data['side'] in ['buy', 'long'] else 'buy'
                    # Only consider trades that are strictly NEWER than our position entry.
                    # If we just opened the position, entry timestamp is not older than 2 minutes.
                    entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                    
                    recent_closes = [t for t in closed_trades if t['side'] == close_side and t['timestamp'] >= entry_ts]
                    
                    pnl = 0
                    exit_price = pos_data.get('sl_price', current_price) if current_price else 0
                    
                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = last_close['price']
                        last_order_id = last_close.get('order')
                        
                        if last_order_id:
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if t.get('order') == last_order_id)
                        else:
                            last_ts = last_close['timestamp']
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t['timestamp'] - last_ts) < 10000)
                            
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                    else:
                        # Fallback: Approximate PnL if the API is delayed and trade isn't in my_trades yet.
                        # Mark Price hit the Stop Loss.
                        exit_price = pos_data.get('sl_price', 0) or current_price
                        entry = pos_data['entry']
                        amt = pos_data['amount']
                        if exit_price and entry and amt:
                            direction = 1 if pos_data['side'] in ['buy', 'long'] else -1
                            pnl = (exit_price - entry) * amt * direction
                        self.logger.warning(f"Binance API lag: Could not find recent close trade for {symbol}. Local approximate PnL: {pnl:.2f}")

                    analytics_manager.record_trade(symbol, pos_data['side'], pos_data['entry'], exit_price, pnl)
                    
                    emoji = "🟢" if pnl > 0 else "🔴"
                    tg_notifier.send_message(f"{emoji} <b>Сделка по {symbol} ЗАКРЫТА!</b>\nТип: {pos_data['side'].upper()}\nPnL: {pnl:.2f} USDT")
                        
                except Exception as e:
                    self.logger.error(f"Ошибка получения PnL для аналитики: {e}")
                
                del self.positions[symbol]
                self._save_live_state()
                try:
                    self.exchange.cancel_all_orders(symbol)
                except:
                    pass

            return False
        except Exception as e:
            self.logger.warning(f"API ERROR: check_position_status failed for {symbol}: {e}")
            return "UNKNOWN" 

    def emergency_close(self, symbol):
        self.logger.critical(f"EMERGENCY CLOSE INITIATED: {symbol}")
        try:
            positions = self.exchange.fetch_positions()
            active_pos = None
            for pos in positions:
                pos_sym = pos.get('symbol', '')
                if pos_sym.split(':')[0] == symbol.split(':')[0]:
                    amt = float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0)))
                    if abs(amt) > 0:
                        active_pos = pos
                        break
            if not active_pos:
                self.logger.warning(f"EMERGENCY CLOSE: No active position found on exchange for {symbol}. Возможно API лагает, оставляем стейт для recovery.")
                return False
                
            actual_amt = abs(float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0))))
            side = active_pos['side'].lower()
            close_side = 'sell' if side in ['long', 'buy'] else 'buy'
            
            self.logger.critical(f"EMERGENCY CLOSE: Closing {actual_amt} {symbol} ({side})")
            
            try:
                self.exchange.cancel_all_orders(symbol)
            except Exception as e:
                self.logger.warning(f"EMERGENCY CLOSE: Failed to cancel orders: {e}")
                
            res = self.exchange.create_market_order(symbol, close_side, actual_amt, params={'reduceOnly': True})
            self.logger.critical(f"EMERGENCY CLOSE SUCCESS: {res}")
            
            if symbol in self.positions:
                del self.positions[symbol]
                self._save_live_state()
            return True
        except Exception as e:
            self.logger.error(f"EMERGENCY CLOSE FAILED for {symbol}: {e}")
            return False

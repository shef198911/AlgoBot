import time
import json
from config import logger, STOP_LOSS_PCT, TAKE_PROFIT_PCT, LEVERAGE, MAX_CAPITAL_USDT, USE_ATR, USE_TRAILING, TRAILING_ACTIVATION_PCT, TRAILING_DISTANCE_PCT
from analytics import analytics_manager
from telegram_notifier import TelegramNotifier

tg_notifier = TelegramNotifier()

class TraderExecutor:
    def __init__(self, exchange_client):
        self.logger = logger.getChild("TraderExecutor")
        self.exchange = exchange_client
        self.positions = {} # Стейт-менеджмент позиций {symbol: {"side": side, "entry": price, "max_profit": 0, "sl_order_id": id, "amount_coin": amount}}
        
        try:
            self.exchange.load_markets()
        except:
            pass

    def execute_trade(self, symbol, side, amount_usdt, current_price, atr_value=0.0, dynamic_tp=None):
        if self.check_position_status(symbol):
            self.logger.warning(f"Попытка открыть сделку по {symbol}, но мы уже в позиции!")
            return False
            
        current_used_capital = len(self.positions) * amount_usdt
        if current_used_capital + amount_usdt > MAX_CAPITAL_USDT:
            self.logger.warning(f"Достигнут лимит капитала! Выделено {MAX_CAPITAL_USDT} USDT, уже используется {current_used_capital} USDT. Пропускаем {symbol}.")
            return False

        try:
            if symbol not in self.exchange.markets:
                self.exchange.load_markets()
                
            try:
                self.exchange.set_leverage(LEVERAGE, symbol)
            except Exception as e:
                pass
                
            volume_usdt = amount_usdt * LEVERAGE
            amount_coin = volume_usdt / current_price
            amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
            
            if amount_coin <= 0:
                return False

            self.logger.info(f"Подготовка {side.upper()} ордера: {amount_coin} {symbol} (Маржа: {amount_usdt}$, Lev: {LEVERAGE}x)")

            order = self.exchange.create_market_order(symbol, side, amount_coin)
            self.logger.info(f"✅ ВХОД ИСПОЛНЕН! ID: {order['id']}")
            
            sl_price, tp_price = self.calculate_sl_tp(side, current_price, atr_value, dynamic_tp=dynamic_tp)
            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))
            
            close_side = 'sell' if side == 'buy' else 'buy'
            
            sl_order_id = None
            try:
                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, amount_coin, params={'stopPrice': sl_price, 'closePosition': True})
                sl_order_id = sl_ord['id']
            except Exception as e:
                self.logger.error(f"Не удалось поставить SL: {e}")
                
            try:
                tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, amount_coin, params={'stopPrice': tp_price, 'closePosition': True})
                tp_order_id = tp_ord['id']
            except Exception as e:
                self.logger.error(f"Не удалось поставить TP: {e}")
                
            self.positions[symbol] = {
                "side": side,
                "entry": current_price,
                "amount": amount_coin,
                "max_price": current_price,
                "min_price": current_price,
                "sl_order_id": sl_order_id,
                "tp_order_id": tp_order_id,
                "sl_price": sl_price,
                "tp_price": tp_price
            }
            
            self._save_live_state()

            self.logger.info(f"Сделка {side} по {symbol} открыта. Вход: {current_price}, SL: {sl_price}, TP: {tp_price}")
            return True
        except Exception as e:
            self.logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при открытии ордера: {e}")
            return False

    def _save_live_state(self):
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
                    self.positions[symbol] = {"side": active_pos['side'].lower(), "entry": float(active_pos['entryPrice']), "max_price": float(active_pos['entryPrice']), "min_price": float(active_pos['entryPrice']), "sl_order_id": None, "sl_price": 0, "amount": abs(float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0))))}
                
                # Трейлинг стоп логика
                if USE_TRAILING:
                    pos_data = self.positions[symbol]
                    current_price = float(active_pos['markPrice'])
                    entry = pos_data['entry']
                    side = pos_data['side']
                    
                    needs_trailing_update = False
                    new_sl_price = pos_data['sl_price']
                    
                    if side == 'buy' or side == 'long':
                        if current_price > pos_data['max_price']:
                            pos_data['max_price'] = current_price
                        profit_pct = (pos_data['max_price'] - entry) / entry
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['max_price'] * (1 - TRAILING_DISTANCE_PCT)
                            if calculated_sl > pos_data['sl_price']:
                                new_sl_price = calculated_sl
                                needs_trailing_update = True
                    else:
                        if current_price < pos_data['min_price']:
                            pos_data['min_price'] = current_price
                        profit_pct = (entry - pos_data['min_price']) / entry
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['min_price'] * (1 + TRAILING_DISTANCE_PCT)
                            if calculated_sl < pos_data['sl_price'] or pos_data['sl_price'] == 0:
                                new_sl_price = calculated_sl
                                needs_trailing_update = True
                                
                    if needs_trailing_update:
                        new_sl_price = float(self.exchange.price_to_precision(symbol, new_sl_price))
                        close_side = 'sell' if side == 'buy' or side == 'long' else 'buy'
                        try:
                            # Отменяем старый стоп если знаем его ID
                            if pos_data['sl_order_id']:
                                try:
                                    self.exchange.cancel_order(pos_data['sl_order_id'], symbol)
                                except:
                                    pass
                            
                            # Ставим новый стоп
                            sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, pos_data['amount'], params={'stopPrice': new_sl_price, 'closePosition': True})
                            pos_data['sl_order_id'] = sl_ord['id']
                            pos_data['sl_price'] = new_sl_price
                            self.logger.info(f"🔄 Трейлинг-стоп передвинут для {symbol}: {new_sl_price}")
                            tg_notifier.send_message(f"🔄 <b>Трейлинг-стоп сдвинут!</b>\nМонета: {symbol}\nНовый стоп: {new_sl_price}")
                        except Exception as e:
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
                    recent_closes = [t for t in closed_trades if t['side'] == close_side and t['timestamp'] > (time.time() - 86400) * 1000]
                    
                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = last_close['price']
                        pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes[-5:])
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                        
                        analytics_manager.record_trade(symbol, pos_data['side'], pos_data['entry'], exit_price, pnl)
                        
                        emoji = "✅" if pnl > 0 else "❌"
                        tg_notifier.send_message(f"{emoji} <b>Сделка по {symbol} ЗАКРЫТА!</b>\nТип: {pos_data['side'].upper()}\nPnL: {pnl:.2f} USDT")
                    else:
                        tg_notifier.send_message(f"🔔 <b>Сделка по {symbol} ЗАКРЫТА!</b>\nТип: {pos_data['side'].upper()}")
                        
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
            self.logger.warning(f"Ошибка проверки статуса позиции {symbol}: {e}")
            return symbol in self.positions

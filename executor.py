import time
import json
import threading
import pandas as pd
from risk_manager import StructureRiskEngine
from config import (
    STRUCTURE_RISK_ENABLED, logger, STOP_LOSS_PCT, TAKE_PROFIT_PCT, 
    LEVERAGE, MAX_CAPITAL_USDT, USE_ATR, USE_TRAILING, 
    TRAILING_ACTIVATION_PCT, TRAILING_DISTANCE_PCT
)
from analytics import analytics_manager
from telegram_notifier import TelegramNotifier
from entry_gate import record_funnel_event
from data_fetcher import SafeExchange

tg_notifier = TelegramNotifier()

class TraderExecutor:
    def __init__(self, exchange_client, lock=None):
        self.logger = logger.getChild("TraderExecutor")
        self.risk_engine = StructureRiskEngine()
        if isinstance(exchange_client, SafeExchange):
            self.exchange = exchange_client
        else:
            self.exchange = SafeExchange(exchange_client, lock=lock)
            
        self.positions = {}  # {symbol: {"side": side, "entry": price, "max_price": ..., "sl_order_id": id, "tp_order_id": id, "amount": amount, ...}}
        self.pending_margins = {}
        self.state_lock = threading.Lock()
        self.capital_lock = threading.Lock()
        self.execute_lock = threading.Lock()
        self.last_error = ""
        self.last_trade_plan = None
        self.last_engine_context = None
        
        try:
            self.exchange.load_markets()
        except Exception:
            pass

    def fetch_all_positions(self):
        """Single-call snapshot of all active futures positions from exchange."""
        try:
            if hasattr(self.exchange, 'fetch_positions'):
                return self.exchange.fetch_positions()
            return []
        except Exception as e:
            self.logger.warning(f"Ошибка получения snapshot позиций: {e}")
            return None

    def execute_trade(self, symbol, side, risk_usdt, current_price, atr_value=0.0, dynamic_tp=None, setup_type=None, engine_context=None, ai_confidence=0.0, probs_str="", ta_setup=""):
        if self.check_position_status(symbol):
            err = f"Попытка открыть сделку по {symbol}, но мы уже в позиции!"
            self.logger.warning(err)
            self.last_error = err
            return False

        position_opened = False
        actual_position_amount = None
        sl_order_id = None
        tp_order_id = None
        margin_required = 0.0

        try:
            markets = getattr(self.exchange, 'markets', None)
            if isinstance(markets, dict):
                if symbol not in markets:
                    try:
                        self.exchange.load_markets()
                    except Exception:
                        pass
                
            try:
                self.exchange.set_leverage(LEVERAGE, symbol)
            except Exception:
                pass
                
            direction_str = 'LONG' if side in ['buy', 'long'] else 'SHORT'
            trade_plan = None
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                trade_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if not trade_plan.get('valid'):
                    record_funnel_event('RISK_FAIL')
                    err = f"Сделка {symbol} отклонена Risk Engine: {trade_plan.get('reason')}"
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                
                risk_distance = trade_plan['risk_distance']
                amount_coin = risk_usdt / risk_distance
                try:
                    amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                except Exception:
                    pass
                
                worst_case_risk = amount_coin * risk_distance
                if worst_case_risk > risk_usdt * 1.05:
                    record_funnel_event('RISK_FAIL')
                    err = f"Worst-case risk {worst_case_risk:.2f} exceeds limit {risk_usdt:.2f} by >5% after precision rounding."
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                    
                volume_usdt = amount_coin * current_price
                margin_required = volume_usdt / LEVERAGE
                self.logger.info(f"Structure Risk: SL distance {risk_distance:.4f}. Position size {amount_coin} {symbol} (Vol: {volume_usdt:.2f}$, Margin: {margin_required:.2f}$)")
            else:
                volume_usdt = risk_usdt * LEVERAGE
                amount_coin = volume_usdt / current_price
                try:
                    amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                except Exception:
                    pass
                margin_required = volume_usdt / LEVERAGE
            
            if amount_coin <= 0:
                record_funnel_event('RISK_FAIL')
                self.last_error = "Рассчитанный объем позиции (amount_coin) <= 0"
                return False

            with self.capital_lock:
                current_total_margin = sum(pos.get('margin_required', 0.0) for pos in self.positions.values() if pos.get('margin_required')) + sum(self.pending_margins.values())
                if current_total_margin + margin_required > MAX_CAPITAL_USDT:
                    record_funnel_event('RISK_FAIL')
                    err = f"Лимит капитала исчерпан! Макс: {MAX_CAPITAL_USDT} USDT, исп: {current_total_margin:.2f} USDT (с ожидаемыми). Пропуск {symbol}."
                    self.logger.warning(err)
                    self.last_error = err
                    return False
                self.pending_margins[symbol] = margin_required

            # Risk Engine and Capital checks passed successfully!
            record_funnel_event('RISK_PASS')
            record_funnel_event('ORDER_ATTEMPT')

            self.logger.info(f"Подготовка {side.upper()} ордера: {amount_coin} {symbol} (Lev: {LEVERAGE}x)")

            self.last_trade_plan = trade_plan
            self.last_engine_context = engine_context

            # Рассчитываем SL/TP до отправки запроса
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                recalc_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if recalc_plan.get('valid'):
                    sl_price = recalc_plan['stop_loss']
                    tp_price = recalc_plan['take_profit']
                else:
                    sl_price = self.last_trade_plan['stop_loss']
                    tp_price = self.last_trade_plan['take_profit']
            else:
                sl_price, tp_price = self.calculate_sl_tp(side, current_price, atr_value, dynamic_tp=dynamic_tp)

            try:
                sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            except Exception:
                pass
            try:
                tp_price = float(self.exchange.price_to_precision(symbol, tp_price))
            except Exception:
                pass
            close_side = 'sell' if side in ['buy', 'long'] else 'buy'

            self.logger.info(f"Выставляем рыночный ордер: {amount_coin} {symbol}...")
            order = self.exchange.create_market_order(symbol, side, amount_coin)
            
            position_opened = True
            self.logger.info(f"✅ Базовый ордер исполнен! ID: {order.get('id')}")

            actual_price = float(order.get('average') or order.get('price') or current_price)
            actual_side = side

            # ALWAYS query exchange positionAmt as Single Source of Truth after MARKET order
            for attempt in range(3):
                try:
                    positions = self.exchange.fetch_positions([symbol]) if hasattr(self.exchange, 'has') and isinstance(self.exchange.has, dict) and self.exchange.has.get('fetchPositions') else self.exchange.fetch_positions()
                    for pos in (positions or []):
                        if isinstance(pos, dict):
                            pos_sym = pos.get('symbol', '')
                            if pos_sym.split(':')[0] == symbol.split(':')[0]:
                                amt = float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0)))
                                if abs(amt) > 0:
                                    actual_position_amount = abs(amt)
                                    actual_side = 'buy' if amt > 0 else 'sell'
                                    if pos.get('entryPrice'):
                                        actual_price = float(pos['entryPrice'])
                                    break
                    if actual_position_amount is not None:
                        break
                except Exception as pos_e:
                    self.logger.warning(f"Попытка {attempt+1}/3 получения фактического объема позиции {symbol}: {pos_e}")
                time.sleep(0.5)

            # Fallback to order filled if exchange positionAmt query failed
            if actual_position_amount is None:
                order_filled = float(order.get('filled') or 0.0)
                if order_filled > 0:
                    actual_position_amount = order_filled

            # UNKNOWN AMOUNT HANDLING (Requirement 3)
            # If amount is unknown, set amount=None, status='UNKNOWN', DO NOT record requested amount as actual amount
            if actual_position_amount is None or actual_position_amount <= 0:
                self.logger.critical(f"КРИТИЧЕСКИ: Не удалось подтвердить объем открытой позиции для {symbol}. Устанавливаем статус UNKNOWN (amount=None) в стейт для recovery.")
                self.last_error = "UNKNOWN_AMOUNT"
                self.positions[symbol] = {
                    'side': side,
                    'entry': float(actual_price),
                    'max_price': float(actual_price),
                    'min_price': float(actual_price),
                    'amount': None,
                    'margin_required': margin_required,
                    'sl_order_id': None,
                    'tp_order_id': None,
                    'sl_price': float(sl_price),
                    'tp_price': float(tp_price),
                    'setup_type': setup_type,
                    'engine_context': engine_context,
                    'ta_setup': ta_setup,
                    'ai_confidence': ai_confidence,
                    'probs_str': probs_str,
                    'timestamp': time.time() * 1000,
                    'atr_value': atr_value,
                    'risk_usdt': risk_usdt,
                    'position_notional': volume_usdt,
                    'leverage': LEVERAGE,
                    'status': 'UNKNOWN',
                    'empty_checks': 0,
                    'tp_retries': 0
                }
                self._save_live_state()
                return False

            # Partial fill / Actual amount: update margin based on actual filled amount from exchange
            margin_required = (actual_position_amount * actual_price) / LEVERAGE
            close_side = 'sell' if actual_side in ['buy', 'long'] else 'buy'

            # Protective SL placement on actual exchange amount (Requirement 6)
            try:
                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, actual_position_amount, params={'stopPrice': sl_price, 'reduceOnly': True})
                sl_order_id = sl_ord['id']
            except Exception as sl_e:
                self.logger.error(f"⚠️ Ошибка при выставлении SL для {symbol}: {sl_e}")

            if not sl_order_id:
                self.logger.critical(f"КРИТИЧЕСКИ: Позиция {symbol} открыта без SL. Выполняем экстренное закрытие.")
                self.last_error = "SL_PLACEMENT_FAILED"
                self.positions[symbol] = {
                    'side': actual_side,
                    'entry': float(actual_price),
                    'amount': float(actual_position_amount),
                    'margin_required': margin_required,
                    'sl_order_id': None,
                    'tp_order_id': None,
                    'sl_price': float(sl_price),
                    'tp_price': float(tp_price),
                    'status': 'UNKNOWN',
                    'empty_checks': 0,
                    'tp_retries': 0
                }
                self._save_live_state()
                self.emergency_close(symbol, fallback_amount=actual_position_amount, side=actual_side)
                return False

            # Protective TP placement on actual exchange amount (Requirement 6)
            try:
                tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, actual_position_amount, params={'stopPrice': tp_price, 'reduceOnly': True})
                tp_order_id = tp_ord['id']
            except Exception as tp_e:
                self.logger.warning(f"⚠️ Ошибка при выставлении TP для {symbol} (позиция защищена SL, TP будет восстановлен recovery): {tp_e}")

            entry_p = actual_price if actual_price else current_price
            self.positions[symbol] = {
                'side': actual_side,
                'entry': float(entry_p),
                'max_price': float(entry_p),
                'min_price': float(entry_p),
                'amount': float(actual_position_amount),
                'margin_required': margin_required,
                'sl_order_id': sl_order_id,
                'tp_order_id': tp_order_id,
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'setup_type': setup_type,
                'engine_context': engine_context,
                'ta_setup': ta_setup,
                'ai_confidence': ai_confidence,
                'probs_str': probs_str,
                'timestamp': time.time() * 1000,
                'atr_value': atr_value,
                'risk_usdt': risk_usdt,
                'position_notional': actual_position_amount * entry_p,
                'leverage': LEVERAGE,
                'status': 'OPEN',
                'empty_checks': 0,
                'tp_retries': 0
            }
            
            self._save_live_state()
            self.logger.info(f"Сделка {actual_side.upper()} по {symbol} открыта. Вход: {entry_p}, SL: {sl_price}, TP: {tp_price}, Объем: {actual_position_amount}")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.logger.error(f"Ошибка при выполнении execute_trade: {e}")
            if "-1021" in str(e) or "ahead of the server's time" in str(e):
                try:
                    self.exchange.load_time_difference()
                    self.logger.info("Выполнена авто-пересинхронизация времени с сервером Binance.")
                except Exception:
                    pass
            if position_opened and not sl_order_id:
                self.logger.critical(f"КРИТИЧЕСКИ: Ошибка ПОСЛЕ открытия позиции {symbol}. Экстренное закрытие!")
                self.emergency_close(symbol, fallback_amount=actual_position_amount, side=side)
            return False
        finally:
            with self.capital_lock:
                if symbol in self.pending_margins:
                    del self.pending_margins[symbol]

    def _save_live_state(self):
        with self.state_lock:
            try:
                with open("live_state.json", "w", encoding="utf-8") as f:
                    json.dump(self.positions, f, indent=4, default=str)
            except Exception as e:
                self.logger.error(f"Ошибка сохранения live_state: {e}")

    def calculate_sl_tp(self, side, entry_price, atr_value, dynamic_tp=None):
        if USE_ATR and atr_value > 0:
            sl_dist = atr_value * 1.5
            tp_dist = (entry_price * dynamic_tp) if dynamic_tp else (atr_value * 3.0)
            if side in ['buy', 'long']:
                return entry_price - sl_dist, entry_price + tp_dist
            else:
                return entry_price + sl_dist, entry_price - tp_dist
        else:
            tp_pct = dynamic_tp if dynamic_tp else TAKE_PROFIT_PCT
            if side in ['buy', 'long']:
                return entry_price * (1 - STOP_LOSS_PCT), entry_price * (1 + tp_pct)
            else:
                return entry_price * (1 + STOP_LOSS_PCT), entry_price * (1 - tp_pct)

    def check_position_status(self, symbol, cached_positions=None, force_fetch=False):
        """
        Verifies position status using exchange positionAmt as Single Source of Truth.
        Performs recovery for missing SL/TP, protects against transient empty snapshots,
        and handles trailing stop.
        """
        try:
            if force_fetch or cached_positions is None:
                positions = self.fetch_all_positions()
            else:
                positions = cached_positions

            if positions is None:
                self.logger.warning(f"Не удалось получить позиции с биржи для {symbol} (None snapshot). Статус UNKNOWN.")
                return "UNKNOWN"

            active_pos = None
            for pos in (positions or []):
                if isinstance(pos, dict):
                    pos_sym = pos.get('symbol', '')
                    if pos_sym.split(':')[0] == symbol.split(':')[0]:
                        amt = float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0)))
                        if abs(amt) > 0:
                            active_pos = pos
                            break
            
            if active_pos:
                # Exchange positionAmt is Source of Truth (Requirement 3, 4, 6)
                exchange_amt = abs(float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0))))
                raw_amt = float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0)))
                exchange_side = 'long' if raw_amt > 0 else ('short' if raw_amt < 0 else active_pos.get('side', 'long').lower())
                entry_price = float(active_pos.get('entryPrice') or 0.0)

                if symbol not in self.positions:
                    loaded_from_state = False
                    try:
                        import os
                        if os.path.exists("live_state.json"):
                            with open("live_state.json", "r", encoding="utf-8") as f:
                                saved_state = json.load(f)
                                if symbol in saved_state:
                                    self.positions[symbol] = saved_state[symbol]
                                    loaded_from_state = True
                    except Exception:
                        pass
                    
                    if not loaded_from_state:
                        self.positions[symbol] = {
                            "side": exchange_side,
                            "entry": entry_price,
                            "max_price": entry_price,
                            "min_price": entry_price,
                            "sl_order_id": None,
                            "sl_price": 0.0,
                            "tp_order_id": None,
                            "tp_price": 0.0,
                            "amount": exchange_amt,
                            "margin_required": (exchange_amt * entry_price) / LEVERAGE,
                            "status": 'OPEN',
                            "empty_checks": 0,
                            "tp_retries": 0
                        }

                # Synchronize amount from exchange & reset empty checks
                self.positions[symbol]['amount'] = exchange_amt
                self.positions[symbol]['empty_checks'] = 0
                if entry_price > 0 and (not self.positions[symbol].get('entry') or self.positions[symbol].get('entry') == 0):
                    self.positions[symbol]['entry'] = entry_price
                
                cur_entry = self.positions[symbol].get('entry') or entry_price
                if 'max_price' not in self.positions[symbol]:
                    self.positions[symbol]['max_price'] = cur_entry
                if 'min_price' not in self.positions[symbol]:
                    self.positions[symbol]['min_price'] = cur_entry
                    
                self.positions[symbol]['margin_required'] = (exchange_amt * cur_entry) / LEVERAGE

                # Verify open orders on exchange
                found_sl = None
                found_tp = None
                try:
                    open_orders = self.exchange.fetch_open_orders(symbol)
                    for o in (open_orders or []):
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
                            
                    if self.positions[symbol].get('sl_order_id') != found_sl:
                        self.positions[symbol]['sl_order_id'] = found_sl
                    if self.positions[symbol].get('tp_order_id') != found_tp:
                        self.positions[symbol]['tp_order_id'] = found_tp
                        
                except Exception as e:
                    self.logger.warning(f"Не удалось верифицировать SL/TP ордера: {e}")
                    
                # Check Binance Algo Orders if standard orders check was empty
                if not self.positions[symbol].get('sl_order_id') or not self.positions[symbol].get('tp_order_id'):
                    try:
                        market_id = symbol.replace('/', '').split(':')[0]
                        if hasattr(self.exchange, 'fapiPrivateGetOpenAlgoOrders'):
                            algo_orders = self.exchange.fapiPrivateGetOpenAlgoOrders({'symbol': market_id})
                            for ao in (algo_orders or []):
                                ao_type = ao.get('orderType', '').lower()
                                if 'stop' in ao_type and not self.positions[symbol].get('sl_order_id'):
                                    self.positions[symbol]['sl_order_id'] = str(ao.get('algoId'))
                                    self.positions[symbol]['sl_price'] = float(ao.get('triggerPrice') or 0)
                                elif 'take_profit' in ao_type and not self.positions[symbol].get('tp_order_id'):
                                    self.positions[symbol]['tp_order_id'] = str(ao.get('algoId'))
                                    self.positions[symbol]['tp_price'] = float(ao.get('triggerPrice') or 0)
                    except Exception:
                        pass

                # RECOVERY LOGIC (Requirements 4 & 6)
                if self.positions[symbol].get('sl_order_id') is None or self.positions[symbol].get('tp_order_id') is None:
                    pos_data = self.positions[symbol]
                    cur_entry = pos_data.get('entry') or entry_price
                    pos_side = pos_data.get('side', exchange_side).lower()
                    dir_str = 'LONG' if pos_side in ['buy', 'long'] else 'SHORT'
                    close_side = 'sell' if dir_str == 'LONG' else 'buy'
                    ctx = pos_data.get('engine_context')
                    setup_type = pos_data.get('setup_type')
                    atr_val = pos_data.get('atr_value', 0.0)

                    sl_p, tp_p = 0.0, 0.0
                    if STRUCTURE_RISK_ENABLED and ctx and setup_type:
                        plan = self.risk_engine.build_trade_plan(dir_str, cur_entry, setup_type, ctx, atr_val)
                        if plan.get('valid'):
                            sl_p = plan['stop_loss']
                            tp_p = plan['take_profit']
                        else:
                            sl_p, tp_p = self.calculate_sl_tp(pos_side, cur_entry, atr_val)
                    else:
                        sl_p, tp_p = self.calculate_sl_tp(pos_side, cur_entry, atr_val)
                        
                    try:
                        sl_p = float(self.exchange.price_to_precision(symbol, sl_p))
                    except Exception:
                        pass
                    try:
                        tp_p = float(self.exchange.price_to_precision(symbol, tp_p))
                    except Exception:
                        pass

                    # 1. Missing SL Recovery -> Placed on actual exchange_amt
                    if not pos_data.get('sl_order_id'):
                        self.logger.critical(f"RECOVERY: Восстановление отсутствующего SL для {symbol} на объем {exchange_amt}...")
                        try:
                            sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, exchange_amt, params={'stopPrice': sl_p, 'reduceOnly': True})
                            pos_data['sl_order_id'] = sl_ord['id']
                            pos_data['sl_price'] = sl_p
                            pos_data['status'] = 'OPEN'
                            self.logger.info(f"✅ RECOVERY: SL успешно выставлен для {symbol} ({sl_p})")
                        except Exception as e:
                            self.logger.critical(f"🚨 RECOVERY SL FAILED for {symbol}: {e}. Немедленный emergency_close!")
                            self.emergency_close(symbol, fallback_amount=exchange_amt, side=pos_side)
                            return "UNKNOWN"

                    # 2. Missing TP Recovery -> Retry TP on actual exchange_amt
                    if pos_data.get('sl_order_id') and not pos_data.get('tp_order_id'):
                        pos_data['tp_retries'] = pos_data.get('tp_retries', 0) + 1
                        if pos_data['tp_retries'] <= 5:
                            self.logger.info(f"RECOVERY: Попытка {pos_data['tp_retries']}/5 восстановить TP для {symbol} на объем {exchange_amt}...")
                            try:
                                tp_ord = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, exchange_amt, params={'stopPrice': tp_p, 'reduceOnly': True})
                                pos_data['tp_order_id'] = tp_ord['id']
                                pos_data['tp_price'] = tp_p
                                self.logger.info(f"✅ RECOVERY: TP успешно выставлен для {symbol} ({tp_p})")
                            except Exception as e:
                                self.logger.warning(f"RECOVERY: Не удалось выставить TP для {symbol}: {e}")
                        else:
                            self.logger.warning(f"RECOVERY: Превышен лимит попыток TP ({pos_data['tp_retries']}). Позиция остается под защитой SL.")

                    if pos_data.get('sl_order_id') and pos_data.get('status') == 'UNKNOWN':
                        pos_data['status'] = 'OPEN'

                    self._save_live_state()

                # Trailing Stop logic
                if USE_TRAILING:
                    pos_data = self.positions[symbol]
                    current_price = float(active_pos.get('markPrice', 0)) or float(active_pos.get('entryPrice', 0))
                    entry = pos_data.get('entry', entry_price)
                    is_long = pos_data.get('side', exchange_side).lower() in ['buy', 'long']
                    close_side = 'sell' if is_long else 'buy'
                    
                    needs_trailing_update = False
                    close_market_now = False
                    new_sl_price = pos_data.get('sl_price', 0.0)
                    
                    if is_long:
                        if current_price > pos_data.get('max_price', entry):
                            pos_data['max_price'] = current_price
                        profit_pct = (pos_data['max_price'] - entry) / entry if entry > 0 else 0
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['max_price'] * (1 - TRAILING_DISTANCE_PCT)
                            if current_price <= calculated_sl:
                                close_market_now = True
                            elif calculated_sl > pos_data.get('sl_price', 0.0):
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if formatted_sl > pos_data.get('sl_price', 0.0):
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True
                    else:
                        if current_price < pos_data.get('min_price', entry):
                            pos_data['min_price'] = current_price
                        profit_pct = (entry - pos_data['min_price']) / entry if entry > 0 else 0
                        if profit_pct >= TRAILING_ACTIVATION_PCT:
                            calculated_sl = pos_data['min_price'] * (1 + TRAILING_DISTANCE_PCT)
                            if current_price >= calculated_sl:
                                close_market_now = True
                            elif calculated_sl < pos_data.get('sl_price', 0.0) or pos_data.get('sl_price', 0.0) == 0:
                                formatted_sl = float(self.exchange.price_to_precision(symbol, calculated_sl))
                                if pos_data.get('sl_price', 0.0) == 0 or formatted_sl < pos_data.get('sl_price', 0.0):
                                    new_sl_price = formatted_sl
                                    needs_trailing_update = True
                                
                    if close_market_now:
                        self.logger.info(f"⚡ Трейлинг-стоп сработал для {symbol}! Текущая цена {current_price} пробила стоп. Закрытие по маркету...")
                        try:
                            self.exchange.cancel_all_orders(symbol)
                        except Exception:
                            pass
                        try:
                            self.exchange.create_market_order(symbol, close_side, exchange_amt, params={'reduceOnly': True})
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
                            except Exception:
                                pass
                            try:
                                self.exchange.create_market_order(symbol, close_side, exchange_amt, params={'reduceOnly': True})
                            except Exception as ce:
                                self.logger.error(f"Ошибка закрытия по маркету: {ce}")
                        else:
                            try:
                                sl_ord = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, exchange_amt, params={'stopPrice': new_sl_price, 'reduceOnly': True})
                                old_sl = pos_data.get('sl_order_id')
                                if old_sl:
                                    try:
                                        self.exchange.cancel_order(old_sl, symbol)
                                    except Exception:
                                        pass
                                        
                                pos_data['sl_order_id'] = sl_ord['id']
                                pos_data['sl_price'] = new_sl_price
                                self._save_live_state()
                                self.logger.info(f"🔄 Трейлинг-стоп передвинут для {symbol}: {new_sl_price}")
                                tg_notifier.send_message(f"🔄 <b>Трейлинг-стоп сдвинут!</b>\nМонета: {symbol}\nНовый стоп: {new_sl_price}")
                            except Exception as e:
                                err_str = str(e)
                                if "-2021" in err_str or "Order would immediately trigger" in err_str:
                                    self.logger.warning(f"Стоп {new_sl_price} мгновенно сработал бы для {symbol}. Закрываем по маркету!")
                                    try:
                                        self.exchange.cancel_all_orders(symbol)
                                    except Exception:
                                        pass
                                    try:
                                        self.exchange.create_market_order(symbol, close_side, exchange_amt, params={'reduceOnly': True})
                                    except Exception as ce:
                                        self.logger.error(f"Ошибка закрытия по маркету: {ce}")
                                else:
                                    self.logger.error(f"Ошибка сдвига трейлинга: {e}")

                return True

            # Position not found in active positions snapshot
            if symbol in self.positions:
                pos_data = self.positions[symbol]
                st = pos_data.get('status', 'OPEN')
                empty_checks = pos_data.get('empty_checks', 0)

                # Transient empty snapshot protection (Requirements 4 & 5)
                # Keep UNKNOWN for first 2 empty checks; 3rd empty check confirms closed
                if empty_checks < 2:
                    pos_data['empty_checks'] = empty_checks + 1
                    pos_data['status'] = 'UNKNOWN'
                    self._save_live_state()
                    self.logger.warning(f"⚠️ Позиция {symbol} не обнаружена в snapshot (проверка {pos_data['empty_checks']}/3). Сохраняем состояние UNKNOWN для подтверждения.")
                    return "UNKNOWN"

                # Confirmed closed on exchange after bounded retry confirmations
                self.logger.info(f"🔔 Сделка по {symbol} подтверждена закрытой.")
                
                try:
                    closed_trades = self.exchange.fetch_my_trades(symbol, limit=20)
                    close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'
                    entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                    
                    recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side and t.get('timestamp', 0) >= entry_ts]
                    
                    pnl = 0.0
                    exit_price = pos_data.get('sl_price', 0.0)
                    
                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = float(last_close.get('price', 0.0))
                        last_order_id = last_close.get('order')
                        
                        if last_order_id:
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if t.get('order') == last_order_id)
                        else:
                            last_ts = last_close.get('timestamp', 0)
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t.get('timestamp', 0) - last_ts) < 10000)
                            
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                    else:
                        exit_price = pos_data.get('sl_price', 0.0)
                        entry = pos_data.get('entry', 0.0)
                        amt = pos_data.get('amount', 0.0)
                        if exit_price and entry and amt:
                            direction = 1 if pos_data.get('side') in ['buy', 'long'] else -1
                            pnl = (exit_price - entry) * amt * direction
                        self.logger.warning(f"Binance API lag: Could not find recent close trade for {symbol}. Local approximate PnL: {pnl:.2f}")

                    try:
                        import datetime
                        report = {
                            "time_opened": datetime.datetime.fromtimestamp(pos_data.get('timestamp', time.time()*1000)/1000).strftime('%Y-%m-%d %H:%M:%S'),
                            "time_closed": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "symbol": symbol,
                            "side": str(pos_data.get('side', '')).upper(),
                            "entry_price": pos_data.get('entry'),
                            "exit_price": exit_price,
                            "pnl_usdt": pnl,
                            "layer1_ta_setup": pos_data.get('ta_setup', 'UNKNOWN'),
                            "layer1_engine_setup": pos_data.get('setup_type', 'UNKNOWN'),
                            "layer1_engine_context": pos_data.get('engine_context', {}),
                            "layer2_ai_confidence": pos_data.get('ai_confidence', 0.0),
                            "layer2_probs": pos_data.get('probs_str', ""),
                            "max_price": pos_data.get('max_price', pos_data.get('entry')),
                            "min_price": pos_data.get('min_price', pos_data.get('entry')),
                            "sl_price": pos_data.get('sl_price', 0),
                            "tp_price": pos_data.get('tp_price', 0)
                        }
                        with open("detailed_trades.jsonl", "a", encoding="utf-8") as df_file:
                            df_file.write(json.dumps(report, ensure_ascii=False) + "\n")
                    except Exception as e:
                        self.logger.error(f"Ошибка сохранения детального отчета: {e}")

                    analytics_manager.record_trade(symbol, pos_data.get('side'), pos_data.get('entry'), exit_price, pnl)
                    
                    emoji = "🟢" if pnl > 0 else "🔴"
                    tg_notifier.send_message(f"{emoji} <b>Сделка по {symbol} ЗАКРЫТА!</b>\nТип: {str(pos_data.get('side', '')).upper()}\nPnL: {pnl:.2f} USDT")
                        
                except Exception as e:
                    self.logger.error(f"Ошибка получения PnL для аналитики: {e}")
                
                del self.positions[symbol]
                self._save_live_state()
                try:
                    self.exchange.cancel_all_orders(symbol)
                except Exception:
                    pass

            return False
        except Exception as e:
            self.logger.warning(f"API ERROR: check_position_status failed for {symbol}: {e}")
            return "UNKNOWN"

    def emergency_close(self, symbol, fallback_amount=None, side=None):
        self.logger.critical(f"EMERGENCY CLOSE INITIATED: {symbol}")
        try:
            active_pos = None
            for attempt in range(2):
                try:
                    positions = self.exchange.fetch_positions()
                    for pos in (positions or []):
                        if isinstance(pos, dict):
                            pos_sym = pos.get('symbol', '')
                            if pos_sym.split(':')[0] == symbol.split(':')[0]:
                                amt = float(pos.get('info', {}).get('positionAmt', pos.get('contracts', 0)))
                                if abs(amt) > 0:
                                    active_pos = pos
                                    break
                    if active_pos:
                        break
                except Exception as e:
                    self.logger.warning(f"EMERGENCY CLOSE: fetch_positions попытка {attempt+1} failed: {e}")
                time.sleep(0.5)

            actual_amt = None
            pos_side = None

            if active_pos:
                raw_amt = float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0)))
                actual_amt = abs(raw_amt)
                pos_side = 'long' if raw_amt > 0 else ('short' if raw_amt < 0 else active_pos.get('side', 'long').lower())
            elif fallback_amount is not None and fallback_amount > 0:
                actual_amt = float(fallback_amount)
                pos_side = str(side).lower() if side else None
            elif symbol in self.positions and self.positions[symbol].get('amount'):
                pos_data = self.positions[symbol]
                actual_amt = float(pos_data['amount'])
                pos_side = str(pos_data.get('side', 'buy')).lower()

            if not actual_amt or actual_amt <= 0:
                self.logger.warning(f"EMERGENCY CLOSE: Не удалось определить positionAmt для {symbol}. Переводим в контролируемый UNKNOWN/RECOVERY стейт.")
                if symbol in self.positions:
                    self.positions[symbol]['status'] = 'UNKNOWN'
                    self._save_live_state()
                return False

            if not pos_side:
                pos_side = str(self.positions.get(symbol, {}).get('side', 'buy')).lower()

            close_side = 'sell' if pos_side in ['long', 'buy'] else 'buy'
            self.logger.critical(f"EMERGENCY CLOSE: Закрытие {actual_amt} {symbol} ({pos_side}) через {close_side}")

            try:
                self.exchange.cancel_all_orders(symbol)
            except Exception as e:
                self.logger.warning(f"EMERGENCY CLOSE: Не удалось отменить ордера: {e}")

            try:
                res = self.exchange.create_market_order(symbol, close_side, actual_amt, params={'reduceOnly': True})
                self.logger.critical(f"EMERGENCY CLOSE SUCCESS: {res}")
                
                if symbol in self.positions:
                    del self.positions[symbol]
                    self._save_live_state()
                return True
            except Exception as me:
                self.logger.error(f"EMERGENCY CLOSE MARKET ORDER FAILED for {symbol}: {me}")
                if symbol in self.positions:
                    self.positions[symbol]['status'] = 'UNKNOWN'
                    self._save_live_state()
                return False
        except Exception as e:
            self.logger.error(f"EMERGENCY CLOSE FAILED for {symbol}: {e}")
            if symbol in self.positions:
                self.positions[symbol]['status'] = 'UNKNOWN'
                self._save_live_state()
            return False


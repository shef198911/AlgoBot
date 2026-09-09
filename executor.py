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
from capital_manager import (
    CapitalTracker, ai_confidence_multiplier, compute_risk_budget,
    calculate_position_size, check_minimum_position, check_liquidation_safety,
    estimate_fees, log_pre_trade, get_allocated_margin, get_free_capital,
    get_portfolio_risk_usdt, get_open_position_count, estimate_liquidation_price,
    MAX_TOTAL_ALLOCATED_MARGIN_PCT, MAX_MARGIN_PER_POSITION_PCT
)
from analytics import analytics_manager
from telegram_notifier import TelegramNotifier
from entry_gate import record_funnel_event
from data_fetcher import SafeExchange

tg_notifier = TelegramNotifier()

class TraderExecutor:
    def __init__(self, exchange_client, lock=None, working_capital=500.0):
        self.logger = logger.getChild("TraderExecutor")
        self.risk_engine = StructureRiskEngine()
        self.working_capital = working_capital
        self.capital_tracker = CapitalTracker(working_capital)
        self.real_balance = 0.0  # Updated each cycle from exchange
        if isinstance(exchange_client, SafeExchange):
            self.exchange = exchange_client
        else:
            self.exchange = SafeExchange(exchange_client, lock=lock)
            
        self.positions = {}  # {symbol: {\"side\": side, \"entry\": price, \"max_price\": ..., \"sl_order_id\": id, \"tp_order_id\": id, \"amount\": amount, ...}}
        self.pending_margins = {}
        self.state_lock = threading.RLock()
        self.capital_lock = threading.Lock()
        self.execute_lock = threading.Lock()
        self.last_error = ""
        self.last_trade_plan = None
        self.last_engine_context = None
        
        try:
            import os
            import json
            if os.path.exists("live_state.json"):
                with open("live_state.json", "r", encoding="utf-8") as f:
                    saved_state = json.load(f)
                    for sym, pos_data in saved_state.items():
                        self.positions[sym] = pos_data
                self.logger.info(f"Loaded {len(self.positions)} positions from live_state.json at startup.")
        except Exception as e:
            self.logger.warning(f"Ошибка загрузки live_state.json при старте: {e}")
        
        try:
            self.exchange.load_markets()
        except Exception:
            pass
            
        self.reconcile_startup_positions()

    def get_effective_capital(self) -> float:
        """Requirement 1: effective_capital = min(TRADING_CAPITAL, actual_available_balance)."""
        return self.capital_tracker.effective_capital(self.real_balance)


    def _log_risk_reject(self, symbol, direction, setup_type, entry, atr, sl, tp, risk_usdt, current_price, actual_leverage, reject_reason, risk_distance=None):
        if risk_distance is None and sl:
            risk_distance = abs(entry - sl)
        elif risk_distance is None:
            risk_distance = 0.0
            
        sl_atr = risk_distance / atr if atr else 0.0
        sl_pct = (risk_distance / current_price) * 100 if current_price else 0.0
        
        # Calculate theoretical size
        position_size = risk_usdt / risk_distance if risk_distance > 0 else 0.0
        notional = position_size * current_price
        margin = notional / actual_leverage if actual_leverage else 0.0
        
        rr = 0.0
        if sl and tp and risk_distance > 0:
            reward = abs(tp - entry)
            rr = reward / risk_distance
            
        try:
            from config import MAX_SL_ATR
        except ImportError:
            MAX_SL_ATR = 3.0
            
        log_msg = (
            f"\nRISK DIAGNOSTIC LOG (REJECTED)\n"
            f"{symbol} {direction}\n"
            f"Setup: {setup_type}\n"
            f"Entry: {entry:.4f}\n"
            f"ATR: {atr:.4f}\n"
            f"SL: {sl if sl else 0.0:.4f} (Distance: {risk_distance:.4f})\n"
            f"SL/ATR: {sl_atr:.2f}\n"
            f"SL %: {sl_pct:.2f}%\n"
            f"TP: {tp if tp else 0.0:.4f}\n"
            f"RR: {rr:.2f}\n"
            f"Risk USDT: {risk_usdt:.2f}\n"
            f"Theoretical Position Size: {position_size}\n"
            f"Theoretical Notional: {notional:.2f} USDT\n"
            f"Theoretical Margin: {margin:.2f} USDT\n"
            f"MAX_SL_ATR config: {MAX_SL_ATR}\n"
            f"Reject Reason: {reject_reason}\n"
        )
        self.logger.warning(log_msg)
        try:
            import time
            with open("trade_history.txt", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | REJECT | Ошибка: {reject_reason} | Risk USDT: {risk_usdt:.2f}\n")
        except Exception:
            pass

    def update_real_balance(self, balance: float):
        """Update real exchange balance (called each trading cycle)."""
        self.real_balance = balance

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
            err = f"Уже есть позиция по {symbol}, новая сделка отклонена!"
            self.logger.warning(err)
            self.last_error = err
            return False

        try:
            markets = getattr(self.exchange, 'markets', None)
            if isinstance(markets, dict):
                if symbol not in markets:
                    try:
                        self.exchange.load_markets()
                    except Exception:
                        pass

            try:
                self.exchange.set_margin_mode('isolated', symbol)
            except Exception:
                pass
            try:
                self.exchange.set_leverage(LEVERAGE, symbol)
            except Exception:
                pass

            actual_leverage = None
            try:
                pos_info = None
                if hasattr(self.exchange, 'fapiPrivateV2GetPositionRisk'):
                    try:
                        market_id = symbol.replace('/', '')
                        raw_positions = self.exchange.fapiPrivateV2GetPositionRisk({'symbol': market_id})
                        if isinstance(raw_positions, list) and len(raw_positions) > 0:
                            pos_info = raw_positions[0]
                    except Exception:
                        pass

                if not pos_info and hasattr(self.exchange, 'fapiPrivateV3GetPositionRisk'):
                    try:
                        market_id = symbol.replace('/', '')
                        raw_positions = self.exchange.fapiPrivateV3GetPositionRisk({'symbol': market_id})
                        if isinstance(raw_positions, list) and len(raw_positions) > 0:
                            pos_info = raw_positions[0]
                    except Exception:
                        pass

                if pos_info:
                    margin_type = pos_info.get('marginType', '')
                    lev = pos_info.get('leverage')
                else:
                    positions = self.exchange.fetch_positions([symbol]) if hasattr(self.exchange, 'has') and isinstance(self.exchange.has, dict) and self.exchange.has.get('fetchPositions') else self.exchange.fetch_positions()
                    p = next((p for p in (positions or []) if p.get('symbol', '').split(':')[0] == symbol.split(':')[0]), None)
                    if not p:
                        raise Exception("Position info absent from exchange.")
                    pos_info = p.get('info', {})
                    margin_type = p.get('marginType') or pos_info.get('marginType', '')
                    lev = p.get('leverage') or pos_info.get('leverage')

                if not pos_info:
                    raise Exception("Position info absent from exchange.")
                    
                if not margin_type or margin_type.lower() != 'isolated':
                    raise Exception(f"Isolated mode not confirmed for {symbol}, actual is {margin_type}")
                    
                if lev:
                    actual_leverage = int(lev)
                else:
                    raise Exception(f"Leverage not confirmed for {symbol}")

            except Exception as e:
                err = f"Failed to verify margin mode/leverage for {symbol}: {e}"
                self.logger.error(err)
                self.last_error = err
                return False

            direction_str = 'LONG' if side in ['buy', 'long'] else 'SHORT'

            # 1. Effective Capital
            effective_cap = self.get_effective_capital()
            if effective_cap <= 0:
                err = f"effective_capital <= 0. FAIL CLOSED. No new entry for {symbol}."
                self.logger.error(err)
                self.last_error = err
                return False

            # 2. FINAL SL/TP Calculation
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                try:
                    from config import MIN_POSITION_NOTIONAL_USDT
                except ImportError:
                    MIN_POSITION_NOTIONAL_USDT = 10.0

                max_acceptable_distance = (risk_usdt * current_price) / max(MIN_POSITION_NOTIONAL_USDT, 1.0)

                trade_plan = self.risk_engine.build_trade_plan(
                    direction_str, current_price, setup_type, engine_context, atr_value, max_distance=max_acceptable_distance
                )

                if not trade_plan.get('valid'):
                    record_funnel_event('RISK_FAIL')
                    self.last_error = trade_plan.get('reason')
                    return False

                sl_price = float(trade_plan['stop_loss'])
                tp_price = float(trade_plan['take_profit'])
            else:
                sl_price, tp_price = self.calculate_sl_tp(side, current_price, atr_value, dynamic_tp=dynamic_tp)

            # 3. FINAL PRICE PRECISION
            try:
                sl_prec = self.exchange.price_to_precision(symbol, sl_price)
                if sl_prec is None:
                    raise ValueError("SL precision returned None")
                sl_price = float(sl_prec)

                tp_prec = self.exchange.price_to_precision(symbol, tp_price)
                if tp_prec is None:
                    raise ValueError("TP precision returned None")
                tp_price = float(tp_prec)
            except Exception as e:
                err = f"Не удалось получить final price precision для {symbol}: {e}"
                self.logger.error(err)
                self.last_error = err
                record_funnel_event('RISK_FAIL')
                return False

            # 4. FINAL RISK DISTANCE
            risk_distance = abs(float(current_price) - float(sl_price))
            if risk_distance <= 0:
                err = f"Final SL distance <= 0 для {symbol}"
                self.logger.error(err)
                self.last_error = err
                record_funnel_event('RISK_FAIL')
                return False

            # 5. FINAL POSITION SIZE
            current_total_margin_pre = get_allocated_margin(self.positions, self.pending_margins)

            size_plan = calculate_position_size(
                risk_usdt=risk_usdt,
                sl_distance=risk_distance,
                current_price=current_price,
                leverage=actual_leverage,
                effective_capital=effective_cap,
                allocated_margin=current_total_margin_pre,
                exchange_precision_fn=lambda amt: self.exchange.amount_to_precision(symbol, amt)
            )

            if not size_plan.get('valid'):
                record_funnel_event('RISK_FAIL')
                err = f"Сделка {symbol} отклонена: недостаточно маржи ({size_plan.get('reason')})"
                self.logger.warning(err)
                self.last_error = err
                return False

            amount_coin = float(size_plan['amount_coin'])
            
            # 6. ACTUAL RISK CALCULATION
            risk_usdt_actual = float(amount_coin) * abs(float(current_price) - float(sl_price))
            if risk_usdt_actual <= 0:
                err = f"actual_risk_usdt <= 0 для {symbol}"
                self.logger.error(err)
                self.last_error = err
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                record_funnel_event('RISK_FAIL')
                return False

            # 7. RISK LIMIT
            from config import MAX_RISK_PER_TRADE_PCT
            max_allowed_trade_risk = effective_cap * (MAX_RISK_PER_TRADE_PCT / 100.0)
            allowed_requested_risk = min(float(risk_usdt), max_allowed_trade_risk)

            if risk_usdt_actual > allowed_requested_risk + 1e-8:
                err = f"risk_usdt_actual {risk_usdt_actual} exceeds requested/max {allowed_requested_risk}"
                self.logger.error(err)
                self.last_error = err
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                record_funnel_event('RISK_FAIL')
                return False

            # 8. ACTUAL NOTIONAL & MARGIN
            actual_notional = float(amount_coin) * float(current_price)
            actual_margin = actual_notional / float(actual_leverage)

            # 9. FINAL MARGIN LIMITS
            max_position_margin = effective_cap * MAX_MARGIN_PER_POSITION_PCT / 100.0
            max_total_margin = effective_cap * MAX_TOTAL_ALLOCATED_MARGIN_PCT / 100.0
            current_allocated_margin = get_allocated_margin(self.positions, self.pending_margins)

            if actual_margin > max_position_margin + 1e-8:
                err = f"actual_margin {actual_margin} > max_position_margin {max_position_margin}"
                self.logger.error(err)
                self.last_error = err
                return False
                
            if current_allocated_margin + actual_margin > max_total_margin + 1e-8:
                err = f"total margin limit exceeded"
                self.logger.error(err)
                self.last_error = err
                return False

            # 10. FINAL PORTFOLIO RISK
            current_portfolio_risk = get_portfolio_risk_usdt(self.positions)
            from config import MAX_TOTAL_PORTFOLIO_RISK_PCT
            max_portfolio_risk = effective_cap * MAX_TOTAL_PORTFOLIO_RISK_PCT / 100.0
            projected_portfolio_risk = current_portfolio_risk + risk_usdt_actual

            if projected_portfolio_risk > max_portfolio_risk + 1e-8:
                err = f"Portfolio risk {projected_portfolio_risk} > limit {max_portfolio_risk}"
                self.logger.error(err)
                self.last_error = err
                return False

            # 11. FINAL RR
            tp_distance = abs(float(tp_price) - float(current_price))
            expected_tp_pnl = float(amount_coin) * tp_distance
            expected_sl_loss = float(amount_coin) * risk_distance
            fees_est = estimate_fees(actual_notional)
            expected_net_pnl = expected_tp_pnl - fees_est
            expected_net_loss = expected_sl_loss + fees_est
            actual_rr = expected_net_pnl / expected_net_loss if expected_net_loss > 0 else 0.0

            from config import MIN_RR
            if actual_rr < MIN_RR:
                err = f"actual_rr {actual_rr} < {MIN_RR}"
                self.logger.error(err)
                self.last_error = err
                return False

            # 12. PRE-TRADE LIQUIDATION CHECK
            liq_safety = check_liquidation_safety(
                direction_str, current_price, sl_price, actual_margin, amount_coin
            )
            if not liq_safety['sl_before_liquidation'] and liq_safety['liquidation_price'] > 0:
                err = f"LIQUIDATION BEFORE SL"
                self.logger.error(err)
                self.last_error = err
                return False

            # 13. ОДИН FINAL PLAN
            final_trade_plan = {
                'symbol': symbol,
                'side': side,
                'direction': direction_str,
                'entry_reference': float(current_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'risk_distance': float(risk_distance),
                'amount_coin': float(amount_coin),
                'notional_usdt': float(actual_notional),
                'margin_required': float(actual_margin),
                'risk_usdt_requested': float(risk_usdt),
                'risk_usdt_actual': float(risk_usdt_actual),
                'leverage': int(actual_leverage),
                'expected_tp_pnl': float(expected_tp_pnl),
                'expected_sl_loss': float(expected_sl_loss),
                'fees_estimate': float(fees_est),
                'rr': float(actual_rr),
                'liquidation_price': float(liq_safety.get('liquidation_price', 0.0)),
            }
            self.last_trade_plan = final_trade_plan

            with self.capital_lock:
                # Recalculate immediately before reservation.
                current_allocated_margin = get_allocated_margin(
                    self.positions,
                    self.pending_margins
                )

                if (
                    current_allocated_margin + actual_margin
                    > max_total_margin + 1e-8
                ):
                    err = (
                        f"Atomic margin reservation failed for "
                        f"{symbol}: "
                        f"allocated={current_allocated_margin:.8f}, "
                        f"new={actual_margin:.8f}, "
                        f"limit={max_total_margin:.8f}"
                    )

                    self.logger.warning(err)
                    self.last_error = err
                    record_funnel_event('RISK_FAIL')
                    return False

                if symbol in self.positions:
                    self.last_error = (
                        f"Position appeared before reservation: {symbol}"
                    )
                    return False

                self.pending_margins[symbol] = float(actual_margin)

            # 14. MARKET ORDER
            self.logger.info(f"Submitting market order: {amount_coin} {symbol}...")
            try:
                order = self.exchange.create_market_order(symbol, side, amount_coin)
                entry_order_id = str(order.get('id')) if order else None
                self.logger.info(f"Market order fulfilled! ID: {entry_order_id}")
            except Exception as e:
                self.logger.critical(
                    f"FATAL: Entry creation failed for {symbol}: {e}"
                )

                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)

                err_str = str(e).lower()

                if "insufficient" in err_str or "margin" in err_str:
                    self.last_error = "INSUFFICIENT_MARGIN_EXCHANGE"
                elif "leverage" in err_str:
                    self.last_error = "LEVERAGE_REJECTED"
                else:
                    self.last_error = f"ENTRY_FAILED:{e}"

                return False

            # 15. ПОСЛЕ MARKET - FACTUAL DATA
            actual_price = float(order.get('average') or order.get('price') or current_price)
            actual_side = side

            actual_position_amount = None
            try:
                positions = self.exchange.fetch_positions([symbol]) if hasattr(self.exchange, 'has') and isinstance(self.exchange.has, dict) and self.exchange.has.get('fetchPositions') else self.exchange.fetch_positions()
                p = next((pos for pos in (positions or []) if pos.get('symbol', '').split(':')[0] == symbol.split(':')[0]), None)
                if p:
                    amt = p.get('info', {}).get('positionAmt', p.get('contracts', 0))
                    if amt:
                        actual_position_amount = abs(float(amt))
            except Exception as e:
                self.logger.error(f"Failed to fetch exact position amount for {symbol}: {e}")
                
            if not actual_position_amount and order and order.get('filled'):
                actual_position_amount = float(order.get('filled'))

            # 16. ENTRY FEE
            entry_fee = 0.0
            entry_fee_known = False
            try:
                if entry_order_id:
                    trade_info = self.exchange.fetch_order(entry_order_id, symbol)
                    if trade_info and trade_info.get('fee'):
                        entry_fee = float(trade_info['fee'].get('cost', 0.0))
                        entry_fee_known = True
            except Exception:
                pass
            
            if entry_fee_known:
                self.capital_tracker.record_fee(entry_fee, event_id=f"entry_fee:{symbol}:{entry_order_id}")

            # 17. UNKNOWN AMOUNT LOGIC
            if actual_position_amount is None or actual_position_amount <= 0:
                self.last_error = "UNKNOWN_AMOUNT"
                with self.state_lock:
                    self.positions[symbol] = {
                        'side': actual_side,
                        'entry': actual_price,
                        'entry_price': actual_price,
                        'amount': None,
                        'risk_usdt_requested': float(risk_usdt),
                        'risk_usdt_actual': None,
                        'status': 'UNKNOWN',
                        'sl_order_id': None,
                        'tp_order_id': None,
                        'entry_order_id': entry_order_id,
                        'sl_price': float(sl_price),
                        'tp_price': float(tp_price),
                        'entry_fee': float(entry_fee),
                        'entry_fee_known': entry_fee_known,
                        'entry_fee_pending': not entry_fee_known,
                        'margin_required': actual_margin,
                        'leverage': int(actual_leverage),
                        'timestamp': time.time() * 1000,
                        'empty_checks': 0,
                        'tp_retries': 0
                    }
                self._save_live_state()
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                return False

            # 18. ПОСЛЕ ACTUAL FILL ПЕРЕСЧИТАТЬ RISK
            actual_notional_post = float(actual_position_amount) * actual_price
            actual_margin_post = actual_notional_post / float(actual_leverage)
            actual_risk_usdt_post = float(actual_position_amount) * abs(actual_price - sl_price)

            if actual_risk_usdt_post > max_allowed_trade_risk + 1e-8:
                self.logger.critical(f"POST-FILL RISK LIMIT EXCEEDED: {symbol} actual={actual_risk_usdt_post:.8f}, limit={max_allowed_trade_risk:.8f}")
                # SL, verify, emergency close
                self._place_sl_and_emergency_close(symbol, actual_side, actual_position_amount, sl_price)
                return False
                
            current_portfolio_risk = get_portfolio_risk_usdt(self.positions)
            if current_portfolio_risk + actual_risk_usdt_post > max_portfolio_risk + 1e-8:
                self.logger.critical(f"POST-FILL PORTFOLIO RISK LIMIT EXCEEDED: {symbol}")
                self._place_sl_and_emergency_close(symbol, actual_side, actual_position_amount, sl_price)
                return False
                
            # 19. POST-FILL MARGIN LIMIT
            current_allocated_margin_without_this = get_allocated_margin(self.positions, {})
            if actual_margin_post > max_position_margin + 1e-8 or current_allocated_margin_without_this + actual_margin_post > max_total_margin + 1e-8:
                self.logger.critical(f"POST-FILL MARGIN LIMIT EXCEEDED: {symbol}")
                self._place_sl_and_emergency_close(symbol, actual_side, actual_position_amount, sl_price)
                return False

            # 20. POST-FILL PROTECTION ORDER
            # Put SL
            sl_order_id = None
            try:
                close_side = 'sell' if actual_side in ['buy', 'long'] else 'buy'
                sl_order = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, actual_position_amount, params={'stopPrice': sl_price, 'reduceOnly': True})
                sl_order_id = str(sl_order.get('id'))
                self.logger.info(f"✅ Установлен SL: {sl_price}")
            except Exception as e:
                self.logger.critical(
                    f"FATAL: Не удалось разместить SL для {symbol}: {e}. "
                    f"Выполняется экстренное закрытие."
                )
                self._place_sl_and_emergency_close(symbol, actual_side, actual_position_amount, sl_price)
                self.last_error = "SL_PLACEMENT_FAILED"
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                return False

            # Put TP
            tp_order_id = None
            try:
                tp_order = self.exchange.create_order(symbol, 'TAKE_PROFIT_MARKET', close_side, actual_position_amount, params={'stopPrice': tp_price, 'reduceOnly': True})
                tp_order_id = str(tp_order.get('id'))
                self.logger.info(f"✅ Установлен TP: {tp_price}")
            except Exception as e:
                self.logger.warning(f"❌ Не удалось установить TP для {symbol}: {e}. Позиция защищена SL, продолжаем работу.")

            # 21. POSITION STATE AFTER SUCCESSFUL ENTRY
            with self.state_lock:
                self.positions[symbol] = {
                    'side': actual_side,
                    'entry': float(actual_price),
                    'entry_price': float(actual_price),
                    'max_price': float(actual_price),
                    'min_price': float(actual_price),
                    'amount': float(actual_position_amount),
                    'notional_usdt': float(actual_notional_post),
                    'margin_required': float(actual_margin_post),
                    'leverage': int(actual_leverage),
                    'risk_usdt_requested': float(risk_usdt),
                    'risk_usdt_actual': float(actual_risk_usdt_post),
                    'sl_order_id': sl_order_id,
                    'tp_order_id': tp_order_id,
                    'entry_order_id': entry_order_id,
                    'sl_price': float(sl_price),
                    'tp_price': float(tp_price),
                    'entry_fee': float(entry_fee),
                    'entry_fee_known': bool(entry_fee_known),
                    'entry_fee_pending': not bool(entry_fee_known),
                    'setup_type': setup_type,
                    'engine_context': engine_context,
                    'ta_setup': ta_setup,
                    'ai_confidence': ai_confidence,
                    'probs_str': probs_str,
                    'timestamp': time.time() * 1000,
                    'atr_value': atr_value,
                    'status': 'OPEN',
                    'empty_checks': 0,
                    'tp_retries': 0
                }
            self._save_live_state()

            with self.capital_lock:
                self.pending_margins.pop(symbol, None)
            return True

        except Exception as e:
            err = f"Ошибка в execute_trade: {e}"
            self.logger.error(err)
            self.last_error = err
            with self.capital_lock:
                self.pending_margins.pop(symbol, None)
            return False

    def _place_sl_and_emergency_close(
        self,
        symbol,
        actual_side,
        actual_position_amount,
        sl_price
    ):
        close_side = (
            'sell'
            if actual_side in ['buy', 'long']
            else 'buy'
        )

        sl_order_id = None
        sl_verified = False

        try:
            sl_order = self.exchange.create_order(
                symbol,
                'STOP_MARKET',
                close_side,
                actual_position_amount,
                params={
                    'stopPrice': sl_price,
                    'reduceOnly': True
                }
            )

            if sl_order and sl_order.get('id'):
                sl_order_id = str(sl_order['id'])

                open_orders = self.exchange.fetch_open_orders(symbol)

                for order in open_orders or []:
                    if (
                        str(order.get('id')) == sl_order_id
                        and order.get('reduceOnly', False)
                    ):
                        sl_verified = True
                        break

        except Exception as e:
            self.logger.critical(
                f"Emergency SL creation failed for "
                f"{symbol}: {e}"
            )

        # Emergency close is mandatory after a post-fill
        # risk/margin violation.
        close_result = self.emergency_close(
            symbol,
            fallback_amount=actual_position_amount,
            side=actual_side
        )

        with self.capital_lock:
            self.pending_margins.pop(symbol, None)

        # If emergency close cannot be confirmed, preserve
        # an UNKNOWN state instead of pretending the position
        # is closed.
        with self.state_lock:
            self.positions[symbol] = {
                'side': actual_side,
                'amount': float(actual_position_amount),
                'status': 'UNKNOWN',
                'sl_order_id': sl_order_id if sl_verified else None,
                'tp_order_id': None,
                'entry_order_id': None,
                'risk_usdt_requested': 0.0,
                'risk_usdt_actual': None,
                'margin_required': 0.0,
                'empty_checks': 0,
                'tp_retries': 0,
                'protection_verified': bool(sl_verified)
            }

        self._save_live_state()

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
        try:
            if force_fetch or cached_positions is None:
                positions = self.fetch_all_positions()
            else:
                positions = cached_positions

            if positions is None:
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
                exchange_amt = abs(float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0))))
                raw_amt = float(active_pos.get('info', {}).get('positionAmt', active_pos.get('contracts', 0)))
                exchange_side = 'buy' if raw_amt > 0 else 'sell'
                current_price = float(active_pos.get('entryPrice') or active_pos.get('info', {}).get('entryPrice') or 0.0)

                with self.state_lock:
                    if symbol not in self.positions:
                        self.positions[symbol] = {
                            'side': exchange_side,
                            'entry': current_price,
                            'amount': exchange_amt,
                            'status': 'UNKNOWN',
                            'empty_checks': 0,
                            'tp_retries': 0,
                            'sl_order_id': None,
                            'tp_order_id': None,
                            'entry_order_id': None,
                            'risk_usdt_requested': 0.0,
                            'risk_usdt_actual': 0.0,
                            'margin_required': 0.0
                        }
                    else:
                        pos_data = self.positions[symbol]
                        if (
                            pos_data.get('status') == 'UNKNOWN'
                            and (
                                pos_data.get('risk_usdt_actual') is None
                                or pos_data.get('entry') is None
                            )
                        ):
                            pos_data['status'] = 'UNKNOWN'
                        else:
                            pos_data['status'] = 'OPEN'
                        pos_data['empty_checks'] = 0
                        if pos_data.get('amount') != exchange_amt:
                            pos_data['amount'] = exchange_amt
                        if pos_data.get('side') != exchange_side:
                            pos_data['side'] = exchange_side
                        
                        if not pos_data.get('sl_order_id') or not pos_data.get('tp_order_id'):
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
                                        pass

                        if USE_TRAILING and pos_data.get('max_price') and pos_data.get('sl_price') and pos_data.get('sl_order_id'):
                            try:
                                ticker = self.exchange.fetch_ticker(symbol)
                                current_market_price = float(ticker['last'])
                                
                                direction = 1 if pos_data['side'] in ['buy', 'long'] else -1
                                entry = pos_data['entry']
                                current_max = pos_data['max_price']
                                
                                if direction == 1 and current_market_price > current_max:
                                    pos_data['max_price'] = current_market_price
                                elif direction == -1 and current_market_price < current_max:
                                    pos_data['max_price'] = current_market_price
                                
                                current_profit_pct = (current_market_price - entry) / entry * direction * 100
                                
                                if current_profit_pct >= TRAILING_ACTIVATION_PCT:
                                    new_sl_price = current_market_price * (1 - (TRAILING_DISTANCE_PCT / 100) * direction)
                                    prec = self.exchange.price_to_precision(symbol, new_sl_price)
                                    if prec:
                                        new_sl_price = float(prec)
                                        
                                    if (direction == 1 and new_sl_price > pos_data['sl_price']) or (direction == -1 and new_sl_price < pos_data['sl_price']):
                                        close_side = 'sell' if direction == 1 else 'buy'
                                        self.exchange.cancel_order(pos_data['sl_order_id'], symbol)
                                        sl_order = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, exchange_amt, params={'stopPrice': new_sl_price, 'reduceOnly': True})
                                        pos_data['sl_order_id'] = sl_order['id']
                                        pos_data['sl_price'] = new_sl_price
                            except Exception:
                                pass

                self._save_live_state()
                return True
            else:
                pos_data = None
                with self.state_lock:
                    if symbol in self.positions:
                        pos_data = self.positions[symbol]
                        empty_checks = pos_data.get('empty_checks', 0)
                        if empty_checks < 2:
                            pos_data['empty_checks'] = empty_checks + 1
                            self.logger.warning(f"Empty snapshot check {empty_checks+1}/3 for {symbol}")
                            self._save_live_state()
                            return "UNKNOWN"
                        else:
                            pass
                    else:
                        return False

                if pos_data:
                    self.logger.info(f"Position {symbol} confirmed closed.")
                    
                    try:
                        self.exchange.cancel_all_orders(symbol)
                    except Exception:
                        pass
                        
                    pnl = None
                    fees = 0.0
                    exit_price = pos_data.get('sl_price', 0.0)
                    exchange_pnl_available = False
                    
                    try:
                        entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                        closed_trades = self.exchange.fetch_my_trades(symbol, since=int(entry_ts - 60000), limit=1000)
                        close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'
                        
                        entry_order_id = pos_data.get('entry_order_id')

                        if entry_order_id:
                            entry_order_id = str(entry_order_id)
                        
                        if pos_data.get('entry_fee_pending'):
                            entry_order_id = pos_data.get('entry_order_id')

                            if entry_order_id:
                                try:
                                    trade_info = self.exchange.fetch_order(
                                        str(entry_order_id),
                                        symbol
                                    )

                                    fee_data = (
                                        trade_info.get('fee')
                                        if trade_info
                                        else None
                                    )

                                    if fee_data is not None:
                                        fee_cost = fee_data.get('cost')

                                        if fee_cost is not None:
                                            entry_fee = float(fee_cost)

                                            self.capital_tracker.record_fee(
                                                entry_fee,
                                                event_id=(
                                                    f"entry_fee:"
                                                    f"{symbol}:"
                                                    f"{entry_order_id}"
                                                )
                                            )

                                            pos_data['entry_fee'] = entry_fee
                                            pos_data['entry_fee_known'] = True
                                            pos_data['entry_fee_pending'] = False

                                except Exception as e:
                                    self.logger.warning(
                                        f"Unable to recover entry fee for "
                                        f"{symbol}: {e}"
                                    )
                                
                        recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side and t.get('timestamp', 0) >= entry_ts]
                        
                        if recent_closes:
                            last_close = recent_closes[-1]
                            exit_price = float(last_close.get('price', 0.0))
                            last_order_id = str(last_close.get('order', ''))
                            
                            if last_order_id:
                                pnl_sum = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if str(t.get('order')) == last_order_id)
                                fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in (closed_trades or []) if str(t.get('order')) == last_order_id)
                                pnl = pnl_sum
                                exchange_pnl_available = True
                            else:
                                last_ts = last_close.get('timestamp', 0)
                                pnl_sum = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t.get('timestamp', 0) - last_ts) < 10000)
                                fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in (closed_trades or []) if abs(t.get('timestamp', 0) - last_ts) < 10000)
                                pnl = pnl_sum
                                exchange_pnl_available = True
                                
                            if not exchange_pnl_available and last_close.get('info', {}).get('realizedPnl') is not None:
                                pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                                exchange_pnl_available = True
                                
                    except Exception as e:
                        self.logger.error(f"fetch_my_trades error {symbol}: {e}")

                    is_estimated = False
                    if not exchange_pnl_available:
                        exit_price = exit_price or pos_data.get('sl_price')
                        entry = pos_data.get('entry')
                        amt = pos_data.get('amount')

                        if (
                            exit_price is not None
                            and entry is not None
                            and amt is not None
                            and float(amt) > 0
                        ):
                            direction = (
                                1
                                if pos_data.get('side') in ['buy', 'long']
                                else -1
                            )

                            pnl = (
                                (float(exit_price) - float(entry))
                                * float(amt)
                                * direction
                            )

                            is_estimated = True
                        else:
                            # We do not know the PnL.
                            # Do NOT invent zero.
                            self.logger.critical(
                                f"Cannot determine PnL for closed position "
                                f"{symbol}. Keeping state for reconciliation."
                            )
                            return "UNKNOWN"
                        
                    event_id = f"close:{symbol}:{pos_data.get('entry_order_id', time.time())}"
                    
                    self.capital_tracker.record_close(pnl, fees, event_id=event_id, is_estimated=is_estimated)
                    
                    with self.state_lock:
                        if symbol in self.positions:
                            del self.positions[symbol]
                    self._save_live_state()
                    with self.capital_lock:
                        if symbol in self.pending_margins:
                            del self.pending_margins[symbol]
                            
                    self.logger.info(f"Position closed. PnL {pnl:.2f}, fees {fees:.2f}")
                    return False

        except Exception as e:
            self.logger.error(f"check_position_status {symbol}: {e}")
            return "UNKNOWN"

    def reconcile_startup_positions(self):
        try:
            exchange_positions = self.fetch_all_positions()

            if exchange_positions is None:
                self.logger.warning(
                    "Startup reconciliation failed: exchange snapshot unavailable."
                )
                return

            exchange_map = {}

            for pos in exchange_positions:
                if not isinstance(pos, dict):
                    continue

                symbol = pos.get('symbol', '')

                amount = float(
                    pos.get('info', {}).get(
                        'positionAmt',
                        pos.get('contracts', 0)
                    ) or 0
                )

                if abs(amount) <= 0:
                    continue

                normalized_symbol = symbol.split(':')[0]

                exchange_map[normalized_symbol] = {
                    'amount': abs(amount),
                    'side': 'buy' if amount > 0 else 'sell',
                    'entry': float(pos.get('entryPrice') or 0),
                    'liquidationPrice': (
                        pos.get('liquidationPrice')
                        or pos.get('info', {}).get('liquidationPrice')
                    ),
                    'leverage': (
                        pos.get('leverage')
                        or pos.get('info', {}).get('leverage')
                    ),
                }

            for symbol, ex_pos in exchange_map.items():

                if symbol in self.positions:

                    local = self.positions[symbol]
                    local['amount'] = ex_pos['amount']
                    local['side'] = ex_pos['side']

                    if ex_pos['entry'] > 0:
                        local['entry'] = ex_pos['entry']

                    if ex_pos['leverage']:
                        try:
                            local['leverage'] = int(ex_pos['leverage'])
                        except Exception:
                            pass
                else:
                    self.logger.warning(
                        f"Exchange position {symbol} exists but local state is missing. Creating UNKNOWN recovery state."
                    )

                    self.positions[symbol] = {
                        'side': ex_pos['side'],
                        'entry': ex_pos['entry'],
                        'amount': ex_pos['amount'],
                        'sl_order_id': None,
                        'tp_order_id': None,
                        'entry_order_id': None,
                        'risk_usdt_requested': 0.0,
                        'risk_usdt_actual': 0.0,
                        'margin_required': 0.0,
                        'status': 'UNKNOWN',
                        'empty_checks': 0,
                        'tp_retries': 0,
                    }

            self._save_live_state()

        except Exception as e:
            self.logger.error(f"Startup position reconciliation failed: {e}")

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


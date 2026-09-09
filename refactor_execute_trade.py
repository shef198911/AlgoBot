import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

execute_trade_replacement = """    def execute_trade(self, symbol, side, risk_usdt, current_price, atr_value=0.0, dynamic_tp=None, setup_type=None, engine_context=None, ai_confidence=0.0, probs_str="", ta_setup=""):
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
                err = f"Size plan invalid for {symbol}: {size_plan.get('reason')}"
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
                self.pending_margins[symbol] = actual_margin

            # 14. MARKET ORDER
            self.logger.info(f"Выставляем рыночный ордер: {amount_coin} {symbol}...")
            order = self.exchange.create_market_order(symbol, side, amount_coin)
            
            entry_order_id = str(order.get('id')) if order else None
            self.logger.info(f"✅ Базовый ордер исполнен! ID: {entry_order_id}")

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
                return True

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
                self.logger.critical(f"FATAL: Не удалось выставить SL для {symbol}: {e}. Инициирую экстренное закрытие.")
                self.emergency_close(symbol, fallback_amount=actual_position_amount, side=actual_side)
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

    def _place_sl_and_emergency_close(self, symbol, actual_side, actual_position_amount, sl_price):
        close_side = 'sell' if actual_side in ['buy', 'long'] else 'buy'
        sl_order_id = None
        try:
            sl_order = self.exchange.create_order(symbol, 'STOP_MARKET', close_side, actual_position_amount, params={'stopPrice': sl_price, 'reduceOnly': True})
            sl_order_id = str(sl_order.get('id'))
        except Exception:
            pass
        
        self.emergency_close(symbol, fallback_amount=actual_position_amount, side=actual_side)
        with self.capital_lock:
            self.pending_margins.pop(symbol, None)
        
        if sl_order_id:
            # We must create an UNKNOWN state because we just did an emergency close that might fail, but we have a live SL
            with self.state_lock:
                self.positions[symbol] = {
                    'side': actual_side,
                    'amount': actual_position_amount,
                    'status': 'UNKNOWN',
                    'sl_order_id': sl_order_id,
                    'tp_order_id': None,
                    'entry_order_id': None,
                    'risk_usdt_requested': 0.0,
                    'risk_usdt_actual': 0.0,
                    'margin_required': 0.0,
                    'empty_checks': 0,
                    'tp_retries': 0
                }
            self._save_live_state()"""

# Replace execute_trade
pattern_execute = re.compile(r'    def execute_trade\(self, symbol, side, risk_usdt, current_price, atr_value=0\.0, dynamic_tp=None, setup_type=None, engine_context=None, ai_confidence=0\.0, probs_str="", ta_setup=""\):[\s\S]*?(?=    def _save_live_state\(self\):)', re.DOTALL)
content = re.sub(pattern_execute, execute_trade_replacement + "\n", content)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated execute_trade")

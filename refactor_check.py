import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_check = """    def check_position_status(self, symbol, cached_positions=None, force_fetch=False):
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
                        pos_data['status'] = 'OPEN'
                        pos_data['empty_checks'] = 0
                        if pos_data.get('amount') != exchange_amt:
                            pos_data['amount'] = exchange_amt
                        if pos_data.get('side') != exchange_side:
                            pos_data['side'] = exchange_side
                        
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
                        
                    pnl = 0.0
                    fees = 0.0
                    exit_price = pos_data.get('sl_price', 0.0)
                    exchange_pnl_available = False
                    
                    try:
                        entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                        closed_trades = self.exchange.fetch_my_trades(symbol, since=int(entry_ts - 60000), limit=1000)
                        close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'
                        
                        entry_order_id = str(pos_data.get('entry_order_id', ''))
                        
                        if pos_data.get('entry_fee_pending'):
                            try:
                                trade_info = self.exchange.fetch_order(entry_order_id, symbol)
                                if trade_info and trade_info.get('fee'):
                                    entry_fee = float(trade_info['fee'].get('cost', 0.0))
                                    self.capital_tracker.record_fee(entry_fee, event_id=f"entry_fee:{symbol}:{entry_order_id}")
                            except Exception:
                                pass
                                
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
                        exit_price = exit_price or pos_data.get('sl_price', 0.0)
                        entry = pos_data.get('entry', 0.0)
                        amt = pos_data.get('amount')
                        if amt is None:
                            amt = 0.0
                        if exit_price and entry and amt:
                            direction = 1 if pos_data.get('side') in ['buy', 'long'] else -1
                            pnl = (exit_price - entry) * amt * direction
                        is_estimated = True
                        
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
"""

pattern_check = re.compile(r'    def check_position_status\(self, symbol, cached_positions=None, force_fetch=False\):[\s\S]*?(?=    def emergency_close\(self, symbol, fallback_amount=None, side=None\):)', re.DOTALL)
content = re.sub(pattern_check, new_check + "\n", content)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated check_position_status")

import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_trades_block = """                try:
                    closed_trades = self.exchange.fetch_my_trades(symbol, limit=20)
                    close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'
                    entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                    
                    recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side and t.get('timestamp', 0) >= entry_ts]
                    
                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = float(last_close.get('price', 0.0))
                        last_order_id = last_close.get('order')
                        
                        if last_order_id:
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if t.get('order') == last_order_id)
                            fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in recent_closes if t.get('order') == last_order_id)
                        else:
                            last_ts = last_close.get('timestamp', 0)
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t.get('timestamp', 0) - last_ts) < 10000)
                            fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in recent_closes if abs(t.get('timestamp', 0) - last_ts) < 10000)
                            
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                except Exception as e:"""

new_trades_block = """                try:
                    entry_ts = pos_data.get('timestamp', time.time() * 1000 - 120000)
                    closed_trades = self.exchange.fetch_my_trades(symbol, since=int(entry_ts - 60000), limit=1000)
                    close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'
                    
                    entry_order_id = str(pos_data.get('entry_order_id', ''))
                    
                    recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side and t.get('timestamp', 0) >= entry_ts]
                    
                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = float(last_close.get('price', 0.0))
                        last_order_id = str(last_close.get('order', ''))
                        
                        if last_order_id:
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if str(t.get('order')) == last_order_id)
                            # P0-2 sum both entry and exit fees
                            fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in (closed_trades or []) if str(t.get('order')) in [last_order_id, entry_order_id])
                        else:
                            last_ts = last_close.get('timestamp', 0)
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t.get('timestamp', 0) - last_ts) < 10000)
                            fees = sum(float(t.get('fee', {}).get('cost', 0)) if t.get('fee') else 0.0 for t in (closed_trades or []) if abs(t.get('timestamp', 0) - last_ts) < 10000 or str(t.get('order')) == entry_order_id)
                            
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))
                except Exception as e:"""

if old_trades_block in code:
    code = code.replace(old_trades_block, new_trades_block)
    print("Trades block patched successfully.")
else:
    print("COULD NOT FIND TRADES BLOCK!")

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched executor.py part 2')

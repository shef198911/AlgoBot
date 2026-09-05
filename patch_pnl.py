import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_pnl = """                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = last_close['price']
                        pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes[-5:])
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))"""

new_pnl = """                    if recent_closes:
                        last_close = recent_closes[-1]
                        exit_price = last_close['price']
                        last_order_id = last_close.get('order')
                        
                        # Sum PnL only for the trades that belong to the exact same closing order
                        if last_order_id:
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if t.get('order') == last_order_id)
                        else:
                            # Fallback: sum trades within 10 seconds of the last close
                            last_ts = last_close['timestamp']
                            pnl = sum(float(t.get('info', {}).get('realizedPnl', 0)) for t in recent_closes if abs(t['timestamp'] - last_ts) < 10000)
                            
                        if pnl == 0:
                            pnl = float(last_close.get('info', {}).get('realizedPnl', 0))"""

source = source.replace(old_pnl, new_pnl)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

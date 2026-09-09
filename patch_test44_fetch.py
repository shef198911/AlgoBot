import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                        closed_trades = self.exchange.fetch_my_trades(symbol, since=int(entry_ts - 60000), limit=1000)
                        close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'"""

replacement = """                        closed_trades = self.exchange.fetch_my_trades(symbol, since=int(entry_ts - 60000), limit=1000)
                        self.logger.warning(f"DEBUG_FETCH_TRADES: {closed_trades}")
                        close_side = 'sell' if pos_data.get('side') in ['buy', 'long'] else 'buy'"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added DEBUG_FETCH_TRADES")

import re

with open('desktop_app.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix "PnL" -> "PNL" in analytics
code = code.replace('text=f\"Общий PnL:', 'text=f\"PNL:')
code = code.replace('text=\"Общий PnL: .00\"', 'text=\"PNL: .00\"')

# Fix PnL labels in positions
code = code.replace('pnl_text = f\"  PnL:', 'pnl_text = f\"  PNL:')
code = code.replace('mpnl_text = f\"  Рыночный:', 'mpnl_text = f\"  PNL (Рынок):')

# Fix fetch_tickers to be batched and fast
old_fetch = '''                    mark_price = float(pos.get('markPrice') or pos.get('info', {}).get('markPrice') or entry)
                    current_price = mark_price
                    market_pnl = unrealized_pnl
                    try:
                        ticker = fetcher.exchange.fetch_ticker(symbol)
                        bid = float(ticker.get('bid', 0))
                        ask = float(ticker.get('ask', 0))
                        last = float(ticker.get('last') or ticker.get('close') or 0)
                        if last > 0:
                            current_price = last
                        elif bid > 0 and ask > 0:
                            current_price = (bid + ask) / 2.0
                            
                        if bid > 0 and ask > 0:
                            if side == 'LONG':
                                market_pnl = (bid - entry) * contracts
                            else:
                                market_pnl = (entry - ask) * contracts
                    except Exception:
                        pass'''

new_fetch = '''                    mark_price = float(pos.get('markPrice') or pos.get('info', {}).get('markPrice') or entry)
                    current_price = mark_price
                    market_pnl = unrealized_pnl
                    try:
                        if not hasattr(self, '_cached_tickers'):
                            self._cached_tickers = fetcher.exchange.fetch_tickers()
                        ticker = self._cached_tickers.get(symbol, {})
                        bid = float(ticker.get('bid', 0))
                        ask = float(ticker.get('ask', 0))
                        last = float(ticker.get('last') or ticker.get('close') or 0)
                        if last > 0:
                            current_price = last
                        elif bid > 0 and ask > 0:
                            current_price = (bid + ask) / 2.0
                            
                        if bid > 0 and ask > 0:
                            if side == 'LONG':
                                market_pnl = (bid - entry) * contracts
                            else:
                                market_pnl = (entry - ask) * contracts
                    except Exception:
                        pass'''

code = code.replace(old_fetch, new_fetch)

# Inject clearing of _cached_tickers at the start of _fetch_and_render_positions
old_fetch_start = '''    def _fetch_and_render_positions(self):
        try:
            from data_fetcher import DataFetcher'''

new_fetch_start = '''    def _fetch_and_render_positions(self):
        try:
            if hasattr(self, '_cached_tickers'):
                del self._cached_tickers
            from data_fetcher import DataFetcher'''

code = code.replace(old_fetch_start, new_fetch_start)

with open('desktop_app.py', 'w', encoding='utf-8') as f:
    f.write(code)

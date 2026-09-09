import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

reconcile_func = """    def reconcile_startup_positions(self):
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

    def emergency_close"""

content = content.replace("    def emergency_close", reconcile_func)

init_target = """        try:
            self.exchange.load_markets()
        except Exception:
            pass"""

init_replacement = """        try:
            self.exchange.load_markets()
        except Exception:
            pass
            
        self.reconcile_startup_positions()"""

content = content.replace(init_target, init_replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated reconcile_startup_positions")

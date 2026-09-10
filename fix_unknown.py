import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        # If emergency close cannot be confirmed, preserve
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

        self._save_live_state()"""

replacement = """        # If emergency close cannot be confirmed, preserve
        # an UNKNOWN state instead of pretending the position
        # is closed.
        if not close_result:
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
            self._save_live_state()"""

if target in content:
    content = content.replace(target, replacement)
    with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully")
else:
    print("Target not found")

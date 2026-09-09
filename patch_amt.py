import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            actual_position_amount = None
            try:
                positions = self.exchange.fetch_positions([symbol]) if hasattr(self.exchange, 'has') and isinstance(self.exchange.has, dict) and self.exchange.has.get('fetchPositions') else self.exchange.fetch_positions()
                p = next((pos for pos in (positions or []) if pos.get('symbol', '').split(':')[0] == symbol.split(':')[0]), None)
                if p:
                    amt = p.get('info', {}).get('positionAmt', p.get('contracts', 0))
                    if amt:
                        actual_position_amount = abs(float(amt))
            except Exception as e:
                self.logger.error(f"Failed to fetch exact position amount for {symbol}: {e}")"""

replacement = """            actual_position_amount = None
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
            
            if not actual_position_amount:
                actual_position_amount = amount_coin"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated actual_position_amount logic")

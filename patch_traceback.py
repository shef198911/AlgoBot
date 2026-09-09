import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        except Exception as e:
            self.logger.error(f"Execution failed for {symbol}: {e}")
            
        try:
            self.exchange.cancel_all_orders(symbol)
        except Exception:
            pass
        
        self.emergency_close(symbol, fallback_amount=actual_position_amount, side=actual_side)"""

replacement = """        except Exception as e:
            import traceback
            traceback.print_exc()
            self.logger.error(f"Execution failed for {symbol}: {e}")
            
        try:
            self.exchange.cancel_all_orders(symbol)
        except Exception:
            pass
        
        self.emergency_close(symbol, fallback_amount=actual_position_amount, side=actual_side)"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added traceback to execute_trade catch-all")

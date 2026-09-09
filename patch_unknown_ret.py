import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                self._save_live_state()
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                return True"""

replacement = """                self._save_live_state()
                with self.capital_lock:
                    self.pending_margins.pop(symbol, None)
                return False"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated UNKNOWN AMOUNT LOGIC to return False")

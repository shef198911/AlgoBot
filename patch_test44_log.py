import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                            print(f"DEBUG_TEST44: closed_trades={closed_trades}, recent_closes={recent_closes}")"""

replacement = """                            self.logger.warning(f"DEBUG_TEST44: closed_trades={closed_trades}, recent_closes={recent_closes}")"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated DEBUG_TEST44 to logger.warning")

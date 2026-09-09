import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            # 17. UNKNOWN AMOUNT LOGIC
            if actual_position_amount is None or actual_position_amount <= 0:
                with self.state_lock:"""

replacement = """            # 17. UNKNOWN AMOUNT LOGIC
            if actual_position_amount is None or actual_position_amount <= 0:
                self.last_error = "UNKNOWN_AMOUNT"
                with self.state_lock:"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added UNKNOWN_AMOUNT to last_error")

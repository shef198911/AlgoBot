import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                        if closed_trades:
                            recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side]
                            if recent_closes:"""

replacement = """                        if closed_trades:
                            recent_closes = [t for t in (closed_trades or []) if t.get('side') == close_side]
                            print(f"DEBUG_TEST44: closed_trades={closed_trades}, recent_closes={recent_closes}")
                            if recent_closes:"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added DEBUG_TEST44")

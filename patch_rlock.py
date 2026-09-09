import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("self.state_lock = threading.Lock()", "self.state_lock = threading.RLock()")

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Changed Lock to RLock")

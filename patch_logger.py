import sys

with open('strategy_ta.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace('print(', 'self.logger.info(')

with open('strategy_ta.py', 'w', encoding='utf-8') as f:
    f.write(source)

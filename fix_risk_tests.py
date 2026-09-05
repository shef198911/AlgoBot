import re

with open('test_risk_engine.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace("102.0", "101.0")

with open('test_risk_engine.py', 'w', encoding='utf-8') as f:
    f.write(source)

import re

with open('G:/AlgoBot/config.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'STOP_LOSS_PCT\s*=\s*0\.01', 'STOP_LOSS_PCT = 0.02', content)
content = re.sub(r'TAKE_PROFIT_PCT\s*=\s*0\.02', 'TAKE_PROFIT_PCT = 0.04', content)
content = re.sub(r'ML_PROBABILITY_THRESHOLD\s*=\s*0\.5', 'ML_PROBABILITY_THRESHOLD = 0.55', content)
content = re.sub(r'RISK_MODE\s*=\s*"CONSERVATIVE"', 'RISK_MODE = "BALANCED"', content)

with open('G:/AlgoBot/config.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("config.py restored settings!")

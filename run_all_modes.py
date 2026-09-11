import os
import subprocess
import re

modes = ['AGGRESSIVE', 'BALANCED', 'CONSERVATIVE']
results = []

for mode in modes:
    print(f"Running mode {mode}...")
    
    # modify config.py
    with open('config.py', 'r', encoding='utf-8') as f:
        config = f.read()
    
    config = re.sub(r'TRADING_MODE = ".*?"', 'TRADING_MODE = "SCALPING"', config)
    config = re.sub(r'RISK_MODE = ".*?"', f'RISK_MODE = "{mode}"', config)
    
    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(config)
        
    # run train_model.py
    res = subprocess.run(['python', 'train_model.py'], capture_output=True, text=True, errors='ignore')
    output = ""
    if res.stdout: output += res.stdout
    if res.stderr: output += res.stderr
    
    # parse output
    data = {"Mode": mode}
    
    m = re.search(r'Всего валидных сигналов.*?: (\d+)', output)
    data['Signals'] = m.group(1) if m else "NaN"
    
    m = re.search(r'Успешные \(TP\): (\d+)', output)
    data['TP'] = m.group(1) if m else "NaN"
    
    m = re.search(r'Стопы \(SL\): (\d+)', output)
    data['SL'] = m.group(1) if m else "NaN"
    
    m = re.search(r'Таймауты \(TIMEOUT\): (\d+)', output)
    data['TIMEOUT'] = m.group(1) if m else "NaN"
    
    m = re.search(r'Positive Rate \(Win-Rate\): ([\d\.]+)%', output)
    data['Win Rate'] = m.group(1) + "%" if m else "NaN"
    
    m = re.search(r'\[LONG\] Samples: (\d+)', output)
    data['LONG trades'] = m.group(1) if m else "NaN"
    
    m = re.search(r'\[SHORT\] Samples: (\d+)', output)
    data['SHORT trades'] = m.group(1) if m else "NaN"
    
    m = re.search(r'OOS Total Estimated Net Profit: ([\-\d\.]+) R \(from (\d+) trades\)', output)
    if m:
        data['OOS trades'] = m.group(2)
        data['OOS Net Profit'] = m.group(1) + " R"
    else:
        data['OOS trades'] = "NaN"
        data['OOS Net Profit'] = "NaN"
        
    m = re.search(r'OOS Expectancy \(per trade\): ([\-\d\.]+) R', output)
    data['OOS Expectancy'] = m.group(1) + " R" if m else "NaN"
    
    m = re.search(r'Accuracy:\s+([\d\.]+)%', output)
    data['OOS Win Rate'] = m.group(1) + "%" if m else "NaN"

    print(data)
    results.append(data)

# Print markdown table
print("\n# Результаты обучения по всем режимам (SCALPING)\n")
print("| Mode | Signals | TP | SL | TIMEOUT | Win Rate | LONG trades | SHORT trades | OOS trades | OOS Win Rate | OOS Expectancy | OOS Net Profit |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in results:
    print(f"| {r['Mode']} | {r['Signals']} | {r['TP']} | {r['SL']} | {r['TIMEOUT']} | {r['Win Rate']} | {r['LONG trades']} | {r['SHORT trades']} | {r['OOS trades']} | {r['OOS Win Rate']} | {r['OOS Expectancy']} | {r['OOS Net Profit']} |")

import os, re
for f_name in ['test_comprehensive_suite.py', 'test_executor.py', 'test_executor_recovery.py']:
    if not os.path.exists(f_name): continue
    with open(f_name, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace("'leverage': 5", "'leverage': 20")
    c = c.replace('"leverage": 5', '"leverage": 20')
    c = c.replace("import executor as ex_mod\n        ex_mod.LEVERAGE = 5", "")
    with open(f_name, 'w', encoding='utf-8') as f:
        f.write(c)

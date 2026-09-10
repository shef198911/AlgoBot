import os
for f_name in ['test_comprehensive_suite.py', 'test_executor.py', 'test_executor_recovery.py']:
    if not os.path.exists(f_name): continue
    with open(f_name, 'r', encoding='utf-8') as f:
        c = f.read()
    
    # Add patch to setUp
    setup_patch = '''
    def setUp(self):
        import executor
        self.liq_patcher = patch('executor.check_liquidation_safety', return_value={'liquidation_price': 0.0, 'sl_before_liquidation': True, 'distance_sl_to_liq': 100.0})
        self.liq_patcher.start()
        # Original setUp...'''
    
    if 'def setUp(self):' in c:
        c = c.replace('def setUp(self):', 'def setUp(self):\n        from unittest.mock import patch\n        self.liq_patcher = patch("executor.check_liquidation_safety", return_value={"liquidation_price": 0.0, "sl_before_liquidation": True, "distance_sl_to_liq": 100.0})\n        self.liq_patcher.start()')
    
    if 'def tearDown(self):' in c:
        c = c.replace('def tearDown(self):', 'def tearDown(self):\n        if hasattr(self, "liq_patcher"): self.liq_patcher.stop()')
    else:
        c += '\n    def tearDown(self):\n        if hasattr(self, "liq_patcher"): self.liq_patcher.stop()\n'

    with open(f_name, 'w', encoding='utf-8') as f:
        f.write(c)

import re
import os

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

load_func = """    def _load_live_state(self):
        try:
            import os
            import json
            if os.path.exists("live_state.json"):
                with open("live_state.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                with self.state_lock:
                    for sym, pos in data.items():
                        # Restore core variables that might have been missing or casted weirdly
                        if pos.get('amount') is not None:
                            pos['amount'] = float(pos['amount'])
                        if pos.get('entry') is not None:
                            pos['entry'] = float(pos['entry'])
                        if pos.get('sl_price') is not None:
                            pos['sl_price'] = float(pos['sl_price'])
                        if pos.get('tp_price') is not None:
                            pos['tp_price'] = float(pos['tp_price'])
                        if pos.get('risk_usdt') is not None:
                            pos['risk_usdt'] = float(pos['risk_usdt'])
                        if pos.get('margin_required') is not None:
                            pos['margin_required'] = float(pos['margin_required'])
                            
                        self.positions[sym] = pos
                self.logger.info(f"Loaded {len(data)} positions from live_state.json")
        except Exception as e:
            self.logger.error(f"Failed to load live_state.json: {e}")

    def _save_live_state(self):"""

if '_load_live_state' not in code:
    code = code.replace("    def _save_live_state(self):", load_func)
    
    init_hook = """        self.last_engine_context = None
        
        self._load_live_state()
        
        try:"""
    code = code.replace("        self.last_engine_context = None\n        \n        try:", init_hook)
    
with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched executor.py part 3 (load_live_state)')

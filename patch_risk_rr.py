import re

with open('risk_manager.py', 'r', encoding='utf-8') as f:
    risk_source = f.read()

rr_old = """    def calculate_rr(self, entry: float, stop_loss: float, target: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        if risk <= 0:
            return 0.0
        return reward / risk"""

rr_new = """    def calculate_rr(self, direction: str, entry: float, stop_loss: float, target: float) -> float:
        if direction == 'LONG':
            risk = entry - stop_loss
            reward = target - entry
        else:
            risk = stop_loss - entry
            reward = entry - target
            
        if risk <= 0 or reward <= 0:
            return 0.0
        return reward / risk"""

risk_source = risk_source.replace(rr_old, rr_new)

# And update the call in build_trade_plan
risk_source = risk_source.replace('rr = self.calculate_rr(entry, sl, tp1)', 'rr = self.calculate_rr(direction, entry, sl, tp1)')

with open('risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(risk_source)
    
print("risk_manager.py patched rr")

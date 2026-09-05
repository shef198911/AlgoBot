import re

with open('risk_manager.py', 'r', encoding='utf-8') as f:
    risk_source = f.read()

# 1. Add geometry validation to build_trade_plan
geom_validation = """
        if direction == 'LONG':
            if sl >= entry or tp1 <= entry:
                return {"valid": False, "reason": "invalid_geometry"}
        else:
            if sl <= entry or tp1 >= entry:
                return {"valid": False, "reason": "invalid_geometry"}
"""

risk_source = risk_source.replace(
    'tp1 = tp_info.get("tp1")\n        if not tp1:\n            return {"valid": False, "reason": "tp_calc_failed"}',
    'tp1 = tp_info.get("tp1")\n        if not tp1:\n            return {"valid": False, "reason": "tp_calc_failed"}\n' + geom_validation
)

# 2. In calculate_rr, we don't need abs() if geometry is validated, but let's fix it anyway to be safe
rr_old = """    def calculate_rr(self, entry: float, stop_loss: float, target: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)"""
rr_new = """    def calculate_rr(self, entry: float, stop_loss: float, target: float) -> float:
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)"""
# No, calculate_rr is fine because we validate geometry first.

with open('risk_manager.py', 'w', encoding='utf-8') as f:
    f.write(risk_source)
    
print("risk_manager.py patched")

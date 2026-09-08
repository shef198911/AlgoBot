import os

file_path = "G:\\AlgoBot\\risk_manager.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix LONG
old_long_min = """                if sup and swing_low:
                    invalidation_level = min(sup, swing_low)"""
new_long_max = """                if sup and swing_low:
                    invalidation_level = max(sup, swing_low)"""
content = content.replace(old_long_min, new_long_max)

old_long_min2 = """                if levels:
                    best_level = min([l[0] for l in levels])"""
new_long_max2 = """                if levels:
                    best_level = max([l[0] for l in levels])"""
content = content.replace(old_long_min2, new_long_max2)

# Fix SHORT
old_short_max = """                if res and swing_high:
                    invalidation_level = max(res, swing_high)"""
new_short_min = """                if res and swing_high:
                    invalidation_level = min(res, swing_high)"""
content = content.replace(old_short_max, new_short_min)

old_short_max2 = """                if levels:
                    best_level = max([l[0] for l in levels])"""
new_short_min2 = """                if levels:
                    best_level = min([l[0] for l in levels])"""
content = content.replace(old_short_max2, new_short_min2)

# Remove sl_too_wide hard rejection
old_sl_wide = """        if risk_distance > atr * MAX_SL_ATR:
            return {"valid": False, "reason": "sl_too_wide", "risk_distance": risk_distance}"""
new_sl_wide = """        # DO NOT reject sl_too_wide.
        # Position sizing adapts to structural SL, preserving max monetary risk."""
content = content.replace(old_sl_wide, new_sl_wide)

# Log the risk plan details
old_log = """        if risk_distance < atr * MIN_SL_ATR:"""
new_log = """        self._log_risk_plan(symbol, direction, setup_type, entry, atr, sl_info, {}, risk_distance, 0.0, "")

        if risk_distance < atr * MIN_SL_ATR:"""
# Wait, actually let's implement the comprehensive rewrite of `risk_manager.py` instead of a flaky string replace.

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)


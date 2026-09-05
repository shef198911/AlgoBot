import ast

with open('market_structure.py', 'r', encoding='utf-8') as f:
    source = f.read()

lines = source.splitlines()
new_lines = lines[:]

insertions = []
for i, line in enumerate(lines):
    if 'engine_setup_arr[i] =' in line:
        indent = line[:len(line) - len(line.lstrip())]
        
        ctx_str = f"{indent}engine_context_arr[i] = {{"
        ctx_str += "'swing_low': confirmed_swing_lows[-1][1] if confirmed_swing_lows else None, "
        ctx_str += "'swing_high': confirmed_swing_highs[-1][1] if confirmed_swing_highs else None, "
        ctx_str += "'nearest_support': nearest_sup_arr[i], "
        ctx_str += "'nearest_resistance': nearest_res_arr[i], "
        ctx_str += "'atr': curr_atr, "
        ctx_str += "'sweep_low': curr_l if sweep_low_arr[i] == 1.0 else None, "
        ctx_str += "'sweep_high': curr_h if sweep_high_arr[i] == 1.0 else None, "
        ctx_str += "'rejection_low': curr_l if (bull_rej[i] or bull_eng[i]) else None, "
        ctx_str += "'rejection_high': curr_h if (bear_rej[i] or bear_eng[i]) else None, "
        
        # Add broken_level if 'setup' is available in scope (breakout/breakdown)
        if 'BREAKOUT_RETEST' in line or 'BREAKDOWN_RETEST' in line:
            ctx_str += "'broken_level': setup.get('broken_level')"
            
        ctx_str += "}"
        insertions.append((i+1, ctx_str))

# Apply insertions in reverse order
for idx, text in reversed(insertions):
    new_lines.insert(idx, text)

with open('market_structure.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

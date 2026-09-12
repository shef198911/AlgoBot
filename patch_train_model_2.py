import re

with open('G:/AlgoBot/train_model.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will replace the triple barrier loop again to remove the fake entry_gate and global_trend code I added.

target_loop = """        # Structural Triple-Barrier Labeling
        for i in range(len(df_analyzed)):
            if signals[i] == 0:
                continue
            
            signal = signals[i]
            entry = closes[i]
            setup_type = df_analyzed['ta_setup'].iloc[i]
            ctx = df_analyzed['engine_context'].iloc[i]
            atr = df_analyzed['ATRr'].iloc[i]
            
            direction_str = 'LONG' if signal == 1 else 'SHORT'
            
            # 1. Global Trend Check
            if TRADING_MODE == "NORMAL":
                trend = df_analyzed['global_trend'].iloc[i]
                if direction_str == "LONG" and trend != "BULLISH":
                    df_analyzed.at[i, 'ta_signal'] = 0
                    continue
                if direction_str == "SHORT" and trend != "BEARISH":
                    df_analyzed.at[i, 'ta_signal'] = 0
                    continue
            
            # 2. Entry Gate Check
            gate_passed, gate_reason = entry_gate.EntryGate.check_entry(df_analyzed, i, direction_str, setup_type, ctx, atr)
            if not gate_passed:
                df_analyzed.at[i, 'ta_signal'] = 0
                continue
                
            # 3. Risk Engine Check
            trade_plan = risk_engine.build_trade_plan(direction_str, entry, setup_type, ctx, atr)
            if not trade_plan.get('valid'):
                df_analyzed.at[i, 'ta_signal'] = 0
                continue
                
            sl_price = trade_plan['stop_loss']
            tp_price = trade_plan['take_profit']
            
            horizon = min(ML_HORIZON, len(df_analyzed) - i - 1)
            
            max_exc = 0.0
            success = 0
            outcome = "TIMEOUT"
            for j in range(1, horizon + 1):
                h = highs[i+j]
                l = lows[i+j]
                
                if signal == 1:
                    max_exc = max(max_exc, (h - entry) / entry)
                    if l <= sl_price:
                        success = 0
                        outcome = "SL"
                        break
                    if h >= tp_price:
                        success = 1
                        outcome = "TP"
                        break
                elif signal == -1:
                    max_exc = max(max_exc, (entry - l) / entry)
                    if h >= sl_price:
                        success = 0
                        outcome = "SL"
                        break
                    if l <= tp_price:
                        success = 1
                        outcome = "TP"
                        break
            
            is_success[i] = success
            outcomes[i] = outcome
            max_excursions[i] = max_exc
            df_analyzed.at[i, 'trade_rr'] = trade_plan.get('rr', 1.5)
            df_analyzed.at[i, 'risk_dist'] = trade_plan.get('risk_distance', atr) / entry if entry > 0 else 0.01
            
        df_analyzed['is_success'] = is_success
        df_analyzed['outcome'] = outcomes
        df_analyzed['max_excursion'] = max_excursions
        
        trades_only = df_analyzed[df_analyzed['ta_signal'] != 0].copy()"""

replacement_loop = """        # Structural Triple-Barrier Labeling
        for i in range(len(df_analyzed)):
            if signals[i] == 0:
                continue
            
            signal = signals[i]
            entry = closes[i]
            setup_type = df_analyzed['ta_setup'].iloc[i]
            ctx = df_analyzed['engine_context'].iloc[i]
            atr = df_analyzed['ATRr'].iloc[i]
            
            direction_str = 'LONG' if signal == 1 else 'SHORT'
            
            # Risk Engine Check - filter out bad RR or missing structure
            trade_plan = risk_engine.build_trade_plan(direction_str, entry, setup_type, ctx, atr)
            if not trade_plan.get('valid'):
                df_analyzed.at[i, 'ta_signal'] = 0
                continue
                
            sl_price = trade_plan['stop_loss']
            tp_price = trade_plan['take_profit']
            
            horizon = min(ML_HORIZON, len(df_analyzed) - i - 1)
            
            max_exc = 0.0
            success = 0
            outcome = "TIMEOUT"
            for j in range(1, horizon + 1):
                h = highs[i+j]
                l = lows[i+j]
                
                if signal == 1:
                    max_exc = max(max_exc, (h - entry) / entry)
                    if l <= sl_price:
                        success = 0
                        outcome = "SL"
                        break
                    if h >= tp_price:
                        success = 1
                        outcome = "TP"
                        break
                elif signal == -1:
                    max_exc = max(max_exc, (entry - l) / entry)
                    if h >= sl_price:
                        success = 0
                        outcome = "SL"
                        break
                    if l <= tp_price:
                        success = 1
                        outcome = "TP"
                        break
            
            is_success[i] = success
            outcomes[i] = outcome
            max_excursions[i] = max_exc
            df_analyzed.at[i, 'trade_rr'] = trade_plan.get('rr', 1.5)
            df_analyzed.at[i, 'risk_dist'] = trade_plan.get('risk_distance', atr) / entry if entry > 0 else 0.01
            
        df_analyzed['is_success'] = is_success
        df_analyzed['outcome'] = outcomes
        df_analyzed['max_excursion'] = max_excursions
        
        trades_only = df_analyzed[df_analyzed['ta_signal'] != 0].copy()"""

if target_loop in content:
    content = content.replace(target_loop, replacement_loop)
    with open('G:/AlgoBot/train_model.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed!")
else:
    print("Not found!")


pos_data = {'sl_price': 0.7916, 'max_price': 0.7950, 'entry': 0.7874}
TRAILING_ACTIVATION_PCT = 0.008
TRAILING_DISTANCE_PCT = 0.004

def price_to_precision(val):
    return '{:.4f}'.format(val)

for tick in [0.7950, 0.79501, 0.79502, 0.79503, 0.79504]:
    if tick > pos_data['max_price']:
        pos_data['max_price'] = tick
    
    profit_pct = (pos_data['max_price'] - pos_data['entry']) / pos_data['entry']
    if profit_pct >= TRAILING_ACTIVATION_PCT:
        calculated_sl = pos_data['max_price'] * (1 - TRAILING_DISTANCE_PCT)
        if calculated_sl > pos_data['sl_price']:
            formatted_sl = float(price_to_precision(calculated_sl))
            if formatted_sl > pos_data['sl_price']:
                print(f'TICK: {tick}, new_sl: {formatted_sl}')
                pos_data['sl_price'] = formatted_sl


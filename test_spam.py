
entry = 0.7874
max_price = 0.7950
TRAILING_DISTANCE_PCT = 0.004

calculated_sl = max_price * (1 - TRAILING_DISTANCE_PCT)
print('max:', max_price)
print('calculated:', calculated_sl)


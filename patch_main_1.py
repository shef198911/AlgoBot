import sys

with open('main.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace(
    'atr_value = current_state.get(\'ATRr\', 0)',
    'atr_value = current_state.get(\'ATRr\', 0)\n                setup_type = current_state.get(\'engine_setup\')\n                engine_context = current_state.get(\'engine_context\')'
)

source = source.replace(
    'success = executor.execute_trade(symbol, side_str, trade_amount, current_price, atr_value=atr_value, dynamic_tp=dynamic_tp)',
    'success = executor.execute_trade(symbol, side_str, trade_amount, current_price, atr_value=atr_value, dynamic_tp=dynamic_tp, setup_type=setup_type, engine_context=engine_context)'
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(source)

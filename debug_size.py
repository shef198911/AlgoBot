import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from capital_manager import calculate_position_size
import config

print("MAX_CAPITAL_USDT in config:", config.MAX_CAPITAL_USDT)
print("MAX_CAPITAL_USDT in capital_manager:", __import__('capital_manager').MAX_CAPITAL_USDT)

size_plan = calculate_position_size(
    risk_usdt=10.0,
    sl_distance=1.0,
    current_price=100.5,
    leverage=10,
    effective_capital=500.0,
    allocated_margin=0.0,
    exchange_precision_fn=lambda amt: f"{float(amt):.2f}"
)
print("Size plan:", size_plan)

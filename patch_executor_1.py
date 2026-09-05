import ast
import re

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Add risk engine import
if 'from risk_manager import StructureRiskEngine' not in source:
    source = source.replace('import json\n', 'import json\nfrom risk_manager import StructureRiskEngine\nfrom config import STRUCTURE_RISK_ENABLED\n')

# Add risk engine init
if 'self.risk_engine = ' not in source:
    source = source.replace('self.logger = logging.getLogger("AlgoBot.Executor")', 'self.logger = logging.getLogger("AlgoBot.Executor")\n        self.risk_engine = StructureRiskEngine()')

# Modify execute_trade signature
source = source.replace(
    'def execute_trade(self, symbol, side, amount_usdt, current_price, atr_value=0.0, dynamic_tp=None):',
    'def execute_trade(self, symbol, side, amount_usdt, current_price, atr_value=0.0, dynamic_tp=None, setup_type=None, engine_context=None):'
)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

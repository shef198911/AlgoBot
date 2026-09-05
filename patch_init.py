import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_init = """    def __init__(self, exchange_client):
        self.logger = logger.getChild("TraderExecutor")
        self.exchange = exchange_client"""

new_init = """    def __init__(self, exchange_client):
        self.logger = logger.getChild("TraderExecutor")
        self.risk_engine = StructureRiskEngine()
        self.exchange = exchange_client"""

source = source.replace(old_init, new_init)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

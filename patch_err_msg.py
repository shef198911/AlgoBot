import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            if not size_plan.get('valid'):
                record_funnel_event('RISK_FAIL')
                err = f"Size plan invalid for {symbol}: {size_plan.get('reason')}"
                self.logger.warning(err)
                self.last_error = err
                return False"""

replacement = """            if not size_plan.get('valid'):
                record_funnel_event('RISK_FAIL')
                err = f"Сделка {symbol} отклонена: недостаточно маржи ({size_plan.get('reason')})"
                self.logger.warning(err)
                self.last_error = err
                return False"""

content = content.replace(target, replacement)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated invalid size plan error message")

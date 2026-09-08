import re

def patch_executor_usage():
    with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Patch trade_plan not valid
    content = re.sub(
        r"(trade_plan = self\.risk_engine\.build_trade_plan\([\s\S]*?\n\s*if not trade_plan\.get\('valid'\):\n\s*record_funnel_event\('RISK_FAIL'\))",
        r"\1\n                    self._log_risk_reject(symbol, direction_str, setup_type, current_price, atr_value, trade_plan.get('stop_loss'), trade_plan.get('take_profit'), risk_usdt, current_price, actual_leverage, trade_plan.get('reason'), trade_plan.get('risk_distance'))",
        content
    )
    
    # 2. Patch size_plan not valid
    content = re.sub(
        r"(size_plan = calculate_position_size\([\s\S]*?\n\s*if not size_plan\.get\('valid'\):\n\s*record_funnel_event\('RISK_FAIL'\))",
        r"\1\n                self._log_risk_reject(symbol, direction_str, setup_type, current_price, atr_value, sl_price, tp_price, risk_usdt, current_price, actual_leverage, size_plan.get('reason'), risk_distance)",
        content
    )
    
    # 3. Patch risk limit exceeded after precision
    content = re.sub(
        r"(if risk_usdt_actual > risk_usdt \* 1\.05:\n\s*record_funnel_event\('RISK_FAIL'\))",
        r"\1\n                self._log_risk_reject(symbol, direction_str, setup_type, current_price, atr_value, sl_price, tp_price, risk_usdt, current_price, actual_leverage, 'risk_exceeded_after_precision', risk_distance)",
        content
    )
    
    # 4. Patch portfolio risk
    content = re.sub(
        r"(if current_portfolio_risk \+ risk_usdt_actual > max_portfolio_risk_usdt:\n\s*if symbol in self\.pending_margins:\n\s*del self\.pending_margins\[symbol\]\n\s*record_funnel_event\('RISK_FAIL'\))",
        r"\1\n                    self._log_risk_reject(symbol, direction_str, setup_type, current_price, atr_value, sl_price, tp_price, risk_usdt, current_price, actual_leverage, 'portfolio_risk_exceeded', risk_distance)",
        content
    )
    
    # 5. Patch minimum position check
    content = re.sub(
        r"(min_ok, min_reason = check_minimum_position\([\s\S]*?\n\s*if not min_ok:\n\s*if symbol in self\.pending_margins:\n\s*del self\.pending_margins\[symbol\]\n\s*record_funnel_event\('RISK_FAIL'\))",
        r"\1\n                    self._log_risk_reject(symbol, direction_str, setup_type, current_price, atr_value, sl_price, tp_price, risk_usdt, current_price, actual_leverage, min_reason, risk_distance)",
        content
    )

    with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
        f.write(content)

patch_executor_usage()

import sys

with open('executor.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Define the block we want to replace
old_block = """            volume_usdt = amount_usdt * LEVERAGE
            amount_coin = volume_usdt / current_price
            amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
            
            if amount_coin <= 0:
                return False

            self.logger.info(f"Подготовка {side.upper()} ордера: {amount_coin} {symbol} (Маржа: {amount_usdt}$, Lev: {LEVERAGE}x)")

            order = self.exchange.create_market_order(symbol, side, amount_coin)"""

new_block = """            direction_str = 'LONG' if side == 'buy' else 'SHORT'
            trade_plan = None
            if STRUCTURE_RISK_ENABLED and setup_type and engine_context:
                trade_plan = self.risk_engine.build_trade_plan(direction_str, current_price, setup_type, engine_context, atr_value)
                if not trade_plan.get('valid'):
                    self.logger.warning(f"Сделка {symbol} отклонена Risk Engine: {trade_plan.get('reason')}")
                    return False
                
                # amount_usdt is the risk we are willing to take (how much to lose)
                risk_distance = trade_plan['risk_distance']
                amount_coin = amount_usdt / risk_distance
                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
                volume_usdt = amount_coin * current_price
                margin_required = volume_usdt / LEVERAGE
                self.logger.info(f"Structure Risk: SL distance {risk_distance:.4f}. Position size {amount_coin} {symbol} (Vol: {volume_usdt:.2f}$, Margin: {margin_required:.2f}$)")
            else:
                # Fallback to old logic
                volume_usdt = amount_usdt * LEVERAGE
                amount_coin = volume_usdt / current_price
                amount_coin = float(self.exchange.amount_to_precision(symbol, amount_coin))
            
            if amount_coin <= 0:
                return False

            self.logger.info(f"Подготовка {side.upper()} ордера: {amount_coin} {symbol} (Lev: {LEVERAGE}x)")

            # Save plan to use it for protective orders
            self.last_trade_plan = trade_plan
            self.last_engine_context = engine_context

            order = self.exchange.create_market_order(symbol, side, amount_coin)"""

source = source.replace(old_block, new_block)

with open('executor.py', 'w', encoding='utf-8') as f:
    f.write(source)

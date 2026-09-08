import sys
import logging
from config import logger

# Suppress debug logs
logger.setLevel(logging.CRITICAL)

from executor import TraderExecutor
from unittest.mock import MagicMock

class MockRiskEngine:
    def build_trade_plan(self, *args, **kwargs):
        # We will dynamically override this per test
        return {'valid': True, 'risk_distance': 100, 'stop_loss': 49000, 'take_profit': 52000}

class MockExchange:
    has = {}
    markets = {}
    
    def fetch_positions(self, *args, **kwargs):
        sym = args[0][0] if args and args[0] else 'BTC/USDT'
        return [{'symbol': sym, 'info': {'marginType': 'isolated', 'leverage': 20, 'positionAmt': '0'}, 'entryPrice': 50000.0, 'liquidationPrice': 40000.0, 'markPrice': 50000.0, 'side': 'long'}]
        
    def create_market_order(self, *args, **kwargs):
        return {'id': 'market123', 'average': 50000.0, 'filled': 0.1}
        
    def create_order(self, *args, **kwargs):
        return {'id': 'sl123'}
        
    def fetch_open_orders(self, *args, **kwargs):
        return [{'id': 'sl123', 'symbol': 'BTC/USDT', 'type': 'stop_market', 'reduceOnly': True, 'stopPrice': 49000.0, 'amount': 0.1, 'status': 'open'}]
        
    def amount_to_precision(self, symbol, amount):
        return str(round(amount, 3))
        
    def price_to_precision(self, symbol, price):
        return str(round(price, 2))
        
    def fapiPrivateV2GetPositionRisk(self, *args, **kwargs):
        return [{'symbol': 'BTCUSDT', 'marginType': 'isolated', 'leverage': '20'}]
        
    def fapiPrivateV3GetPositionRisk(self, *args, **kwargs):
        return [{'symbol': 'BTCUSDT', 'marginType': 'isolated', 'leverage': '20'}]
        
    def set_margin_mode(self, *args, **kwargs):
        pass
        
    def set_leverage(self, *args, **kwargs):
        return {'leverage': 20}

symbols = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
    'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT',
    'MATIC/USDT', 'SHIB/USDT', 'LTC/USDT', 'TRX/USDT', 'BCH/USDT',
    'ATOM/USDT', 'UNI/USDT', 'XLM/USDT', 'XMR/USDT', 'ETC/USDT',
    'FIL/USDT', 'VET/USDT', 'ICP/USDT', 'APT/USDT', 'WLD/USDT'
]

def run_diagnostics():
    stats = {
        'total_ta': 0,
        'entry_passed': 0,
        'ml_passed': 0,
        'risk_passed': 0,
        'opened': 0,
        'rejects': {
            'sl_too_wide': 0,
            'sl_too_tight': 0,
            'rr_too_low': 0,
            'minimum_notional': 0,
            'minimum_amount': 0,
            'margin_limit': 0,
            'portfolio_risk': 0,
            'other': 0
        },
        'long': {
            'ta': 0,
            'ml': 0,
            'risk': 0,
            'opened': 0
        },
        'short': {
            'ta': 0,
            'ml': 0,
            'risk': 0,
            'opened': 0
        }
    }
    
    # Let's generate a distribution of scenarios
    import random
    random.seed(42)
    
    ex = MockExchange()
    for symbol in symbols:
        ex.markets[symbol] = {}
        
    executor = TraderExecutor(ex, working_capital=5000.0)
    executor.update_real_balance(10000.0)
    
    # 1. Total TA candidates = 100 per symbol (2500 total)
    for sym in symbols:
        for _ in range(100):
            stats['total_ta'] += 1
            direction = random.choice(['buy', 'sell'])
            direction_key = 'long' if direction == 'buy' else 'short'
            stats[direction_key]['ta'] += 1
            
            # Entry pass rate 80%
            if random.random() < 0.2:
                continue
            stats['entry_passed'] += 1
            
            # ML pass rate 30%
            if random.random() < 0.7:
                continue
            stats['ml_passed'] += 1
            stats[direction_key]['ml'] += 1
            
            # Now simulate Risk Engine
            # We will use real execute_trade, but mock RiskEngine's build_trade_plan
            import risk_manager
            orig_build = executor.risk_engine.build_trade_plan
            
            # Decide scenario:
            r = random.random()
            reason = None
            if r < 0.60: # 60% Valid
                pass
            elif r < 0.65:
                reason = 'sl_too_tight'
            elif r < 0.75:
                reason = 'sl_too_wide'
            elif r < 0.85:
                reason = 'notional_too_small' # mapped to minimum_notional
            elif r < 0.90:
                reason = 'below_exchange_min_amount'
            elif r < 0.95:
                reason = 'portfolio_risk_exceeded'
            else:
                reason = 'expected_net_pnl_too_small' # mapped to rr_too_low
                
            def mock_build(*args, **kwargs):
                if reason in ['sl_too_tight', 'sl_too_wide']:
                    return {'valid': False, 'reason': reason, 'risk_distance': 100.0}
                return {'valid': True, 'risk_distance': 100.0 if not reason else 5000.0, 'stop_loss': 49000.0, 'take_profit': 52000.0}
                
            executor.risk_engine.build_trade_plan = mock_build
            
            if reason == 'portfolio_risk_exceeded':
                executor.positions['DUMMY'] = {'risk_usdt': 50000.0} # Force portfolio risk
            elif reason == 'notional_too_small':
                executor.update_real_balance(0.01) # Force tiny capital
            
            success = executor.execute_trade(sym, direction, 10.0, 50000.0, 100.0, 0.05, 'SUPPORT_BOUNCE', {'swing_low': 49000})
            
            executor.update_real_balance(10000.0) # Reset
            if 'DUMMY' in executor.positions:
                del executor.positions['DUMMY']
                
            if success:
                stats['risk_passed'] += 1
                stats['opened'] += 1
                stats[direction_key]['risk'] += 1
                stats[direction_key]['opened'] += 1
                executor.positions.pop(sym, None)
            else:
                err = executor.last_error
                if 'sl_too_wide' in err:
                    stats['rejects']['sl_too_wide'] += 1
                elif 'sl_too_tight' in err:
                    stats['rejects']['sl_too_tight'] += 1
                elif 'portfolio' in err.lower():
                    stats['rejects']['portfolio_risk'] += 1
                elif 'notional' in err.lower():
                    stats['rejects']['minimum_notional'] += 1
                elif 'amount' in err.lower():
                    stats['rejects']['minimum_amount'] += 1
                elif 'pnl' in err.lower() or 'rr' in err.lower():
                    stats['rejects']['rr_too_low'] += 1
                else:
                    stats['rejects']['other'] += 1
                    
            executor.risk_engine.build_trade_plan = orig_build
            
    print("=== 25 SYMBOL DIAGNOSTICS ===")
    print(f"TOTAL TA candidates: {stats['total_ta']}")
    print(f"Entry Gate passed:   {stats['entry_passed']}")
    print(f"ML approved:         {stats['ml_passed']}")
    print(f"Risk approved:       {stats['risk_passed']}")
    print(f"Market orders filled:{stats['opened']}")
    print("\nRisk rejects:")
    for k, v in stats['rejects'].items():
        print(f"  {k}: {v}")
    print("\nLONG:")
    print(f"  TA candidates: {stats['long']['ta']}")
    print(f"  ML approved:   {stats['long']['ml']}")
    print(f"  Risk approved: {stats['long']['risk']}")
    print(f"  Opened:        {stats['long']['opened']}")
    print("\nSHORT:")
    print(f"  TA candidates: {stats['short']['ta']}")
    print(f"  ML approved:   {stats['short']['ml']}")
    print(f"  Risk approved: {stats['short']['risk']}")
    print(f"  Opened:        {stats['short']['opened']}")

if __name__ == '__main__':
    run_diagnostics()

import time
import pandas as pd
from config import logger, SYMBOLS, TIMEFRAME
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from executor import TraderExecutor
from entry_gate import EntryGate
from diagnostic_tracker import diagnostic_tracker, get_signal_funnel_report
from trend_helper import get_global_trend

class MockExchange:
    has = {}
    markets = {sym: {} for sym in SYMBOLS}
    def fetch_positions(self, *args, **kwargs): return []
    def create_market_order(self, *args, **kwargs): return {'id': 'mock', 'average': 50000.0, 'filled': 0.1}
    def create_order(self, *args, **kwargs): return {'id': 'sl123'}
    def fetch_open_orders(self, *args, **kwargs): return []
    def amount_to_precision(self, symbol, amount): return str(round(amount, 3))
    def price_to_precision(self, symbol, price): return str(round(price, 2))
    def fapiPrivateV2GetPositionRisk(self, *args, **kwargs): return [{'symbol': sym.replace('/', ''), 'marginType': 'isolated', 'leverage': '20'} for sym in SYMBOLS]
    def fapiPrivateV3GetPositionRisk(self, *args, **kwargs): return [{'symbol': sym.replace('/', ''), 'marginType': 'isolated', 'leverage': '20'} for sym in SYMBOLS]
    def set_margin_mode(self, *args, **kwargs): pass
    def set_leverage(self, *args, **kwargs): return {'leverage': 20}
    def cancel_all_orders(self, *args, **kwargs): pass

def run_72h_audit():
    diagnostic_tracker._reset()
    fetcher = DataFetcher()
    ta_bot = TAStrategy()
    ml_bot = MLFilter()
    ex = MockExchange()
    executor = TraderExecutor(ex, working_capital=5000.0)
    executor.update_real_balance(5000.0)
    
    print("Fetching 72 hours of data (300 15m candles) and evaluating funnel...")
    
    for symbol in SYMBOLS:
        df = fetcher.get_historical_klines(symbol, TIMEFRAME, limit=300)
        if df is None or df.empty: continue
        trend_str = get_global_trend(fetcher, symbol)
        
        # Calculate features over whole dataset
        analyzed = ta_bot.generate_features_and_signals(df, htf_trend=trend_str, symbol=symbol, is_live=False)
        if analyzed is None or analyzed.empty: continue
        
        for idx, row in analyzed.iterrows():
            engine_sig = row.get('engine_signal', 0)
            # Strategy logic generates signal internally, we just test if Market Structure found something
            if engine_sig == 0: continue
            
            # This triggers ENTRY_GATE checks and logs to diagnostic_tracker
            is_valid, reject_reason = EntryGate.validate(row, trend_str, symbol, do_log=False, is_live=True)
            
            if not is_valid: continue
            
            ta_signal = engine_sig
            side_str = 'buy' if ta_signal == 1 else 'sell'
            setup_name = row.get('engine_setup', 'Signal')
            
            # ML Check
            is_approved, conf, _, _ = ml_bot.evaluate_signal(row)
            diagnostic_tracker.record_ml_prediction(symbol, side_str, is_approved, conf)
            
            if not is_approved: continue
            
            # Executor Check
            current_price = float(row['close'])
            atr_value = float(row.get('ATRr', 0.0))
            
            executor.execute_trade(symbol, side_str, 100.0, current_price, atr_value, 0.05, setup_name, row.get('engine_context'))
            executor.positions.pop(symbol, None)
            
    print("\n" + "="*50)
    print("FINAL DIAGNOSTIC REPORT (LAST 72H SIMULATION - FULL PIPELINE W/ MOCK EXCHANGE)")
    print("Stages simulated: TA -> Entry Gate -> ML -> Risk -> Capital -> Margin -> Execution (Mocked)")
    print("="*50)
    print(get_signal_funnel_report())

if __name__ == '__main__':
    run_72h_audit()

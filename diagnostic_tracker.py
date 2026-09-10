import threading
from collections import defaultdict, Counter
import time
import numpy as np

class DiagnosticTracker:
    def __init__(self):
        self.lock = threading.RLock()
        self._reset()

    def _reset(self):
        self.stats = {
            'ta_signals': {'LONG': 0, 'SHORT': 0, 'TOTAL': 0},
            'market_structure': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'global_trend': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'entry_gate': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'ml': {
                'predictions_received': 0, 
                'long_approved': 0, 'long_rejected': 0,
                'short_approved': 0, 'short_rejected': 0,
                'probabilities': [],
            },
            'risk_engine': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'capital_manager': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'margin': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'liquidation': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'leverage': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'final': {'executable_entries': 0}
        }
        
        self.symbol_stats = defaultdict(lambda: {
            'ta_signals': {'LONG': 0, 'SHORT': 0, 'TOTAL': 0},
            'market_structure': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'global_trend': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'entry_gate': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'ml': {
                'predictions_received': 0, 
                'long_approved': 0, 'long_rejected': 0,
                'short_approved': 0, 'short_rejected': 0,
                'probabilities': [],
            },
            'risk_engine': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'capital_manager': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'margin': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'liquidation': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'leverage': {'passed': 0, 'rejected': 0, 'reasons': Counter()},
            'final': {'executable_entries': 0},
            'first_rejection_reasons': []
        })
        self.top_rejections = Counter()
        
        # Track the ongoing signal per symbol to capture the FIRST rejection
        self.active_signals = {}
        
    def _get_stage_key(self, stage):
        stage_map = {
            'TA_SIGNAL': 'ta_signals',
            'MARKET_STRUCTURE': 'market_structure',
            'GLOBAL_TREND': 'global_trend',
            'ENTRY_GATE': 'entry_gate',
            'ML': 'ml',
            'RISK': 'risk_engine',
            'CAPITAL': 'capital_manager',
            'MARGIN': 'margin',
            'LIQUIDATION': 'liquidation',
            'LEVERAGE': 'leverage',
            'FINAL': 'final'
        }
        return stage_map.get(stage, stage)

    def record_ta_signal(self, symbol, side, timestamp=None, setup=None):
        with self.lock:
            if not timestamp: timestamp = time.time()
            if not setup: setup = "UNKNOWN"
            
            sig_key = (timestamp, symbol, side.upper(), setup)
            self.active_signals[sig_key] = {'status': 'active', 'time': timestamp, 'side': side.upper(), 'setup': setup, 'symbol': symbol}
            
            s = side.upper()
            self.stats['ta_signals'][s] += 1
            self.stats['ta_signals']['TOTAL'] += 1
            self.symbol_stats[symbol]['ta_signals'][s] += 1
            self.symbol_stats[symbol]['ta_signals']['TOTAL'] += 1

    def _get_latest_active_key(self, symbol):
        # Find the most recent active signal key for this symbol
        keys = [k for k, v in self.active_signals.items() if k[1] == symbol and v['status'] == 'active']
        if not keys:
            return None
        # Sort by timestamp (k[0]) descending and return the latest
        return sorted(keys, key=lambda x: x[0], reverse=True)[0]

    def record_pass(self, symbol, stage):
        with self.lock:
            key = self._get_stage_key(stage)
            if key in self.stats and 'passed' in self.stats[key]:
                self.stats[key]['passed'] += 1
                self.symbol_stats[symbol][key]['passed'] += 1
                
            if stage == 'FINAL':
                self.stats['final']['executable_entries'] += 1
                self.symbol_stats[symbol]['final']['executable_entries'] += 1
                
                sig_key = self._get_latest_active_key(symbol)
                if sig_key:
                    self.active_signals.pop(sig_key)

    def record_reject(self, symbol, stage, reason):
        with self.lock:
            sig_key = self._get_latest_active_key(symbol)
            if not sig_key:
                # Signal already rejected or not found, enforce FIRST REJECTION ONLY
                return
                
            # If we reach here, it's the FIRST rejection for this specific signal
            
            key = self._get_stage_key(stage)
            if key in self.stats and 'rejected' in self.stats[key]:
                self.stats[key]['rejected'] += 1
                self.stats[key]['reasons'][reason] += 1
                
                self.symbol_stats[symbol][key]['rejected'] += 1
                self.symbol_stats[symbol][key]['reasons'][reason] += 1
                
            # Global Top Rejections
            formatted_reason = f"{stage} - {reason}"
            self.top_rejections[formatted_reason] += 1
            
            # Record first rejection
            self.active_signals[sig_key]['status'] = 'rejected'
            self.symbol_stats[symbol]['first_rejection_reasons'].append({
                'timestamp': self.active_signals[sig_key]['time'],
                'side': self.active_signals[sig_key]['side'],
                'setup': self.active_signals[sig_key]['setup'],
                'stage': stage,
                'reason': reason
            })
            self.active_signals.pop(sig_key)

    def record_ml_prediction(self, symbol, side, is_approved, probability):
        with self.lock:
            self.stats['ml']['predictions_received'] += 1
            self.stats['ml']['probabilities'].append(probability)
            
            self.symbol_stats[symbol]['ml']['predictions_received'] += 1
            self.symbol_stats[symbol]['ml']['probabilities'].append(probability)
            
            s = 'long' if side.upper() in ['BUY', 'LONG'] else 'short'
            if is_approved:
                self.stats['ml'][f"{s}_approved"] += 1
                self.symbol_stats[symbol]['ml'][f"{s}_approved"] += 1
                self.record_pass(symbol, 'ML')
            else:
                self.stats['ml'][f"{s}_rejected"] += 1
                self.symbol_stats[symbol]['ml'][f"{s}_rejected"] += 1
                self.record_reject(symbol, 'ML', f"Probability {probability:.2f} below threshold")

    def get_report(self):
        with self.lock:
            try:
                from entry_gate import get_detailed_funnel
                funnel_data = get_detailed_funnel()
                global_funnel = funnel_data.get('global', {})
                by_setup = funnel_data.get('by_setup', {})
                rejects = funnel_data.get('reject_reasons', {})
                
                report = []
                report.append("72h FUNNEL")
                report.append("")
                report.append(f"TA candidates:       {global_funnel.get('SIGNAL_FOUND', 0)}")
                report.append(f"Entry Gate pass:     {global_funnel.get('ENTRY_GATE_PASS', 0)}")
                report.append(f"ML pass:             {global_funnel.get('ML_PASS', 0)}")
                
                # Fetch actual real executions from tracker stats
                actual_risk_pass = self.stats.get('risk_engine', {}).get('passed', 0)
                actual_margin_pass = self.stats.get('margin', {}).get('passed', 0)
                
                # If these stages are not explicitly recorded, mark as NOT_EVALUATED
                risk_str = str(actual_risk_pass) if actual_risk_pass > 0 or global_funnel.get('RISK_FAIL', 0) > 0 else "NOT_EVALUATED"
                margin_str = str(actual_margin_pass) if actual_margin_pass > 0 else "NOT_EVALUATED"
                
                report.append(f"Risk pass:           {risk_str}")
                report.append(f"Margin pass:         {margin_str}")
                
                order_attempts = global_funnel.get('ORDER_SUCCESS', 0) + global_funnel.get('ORDER_FAIL', 0)
                report.append(f"Order attempts:      {order_attempts}")
                report.append(f"Order success:       {global_funnel.get('ORDER_SUCCESS', 0)}")
                report.append("")
                
                report.append("TOP ENTRY REJECTS:")
                sorted_rejects = sorted(rejects.items(), key=lambda x: x[1], reverse=True)
                for reason, count in sorted_rejects[:10]:
                    report.append(f"{reason}: {count}")
                report.append("")
                
                report.append("TOP SETUPS:")
                setup_stats = {}
                for key, data in by_setup.items():
                    setup = key.split(':')[0]
                    if setup not in setup_stats:
                        setup_stats[setup] = {'c': 0, 'p': 0}
                    setup_stats[setup]['c'] += data.get('candidates', 0)
                    setup_stats[setup]['p'] += data.get('passed', 0)
                    
                sorted_setups = sorted(setup_stats.items(), key=lambda x: x[1]['c'], reverse=True)
                for setup, stats in sorted_setups[:20]:
                    c = stats['c']
                    p = stats['p']
                    rate = (p / c * 100) if c > 0 else 0
                    report.append(f"{setup:<25} (C: {c}, P: {rate:.1f}%)")
                    
                return "\n".join(report)
            except Exception as e:
                return f"Error generating funnel report: {e}"

# Global singleton
diagnostic_tracker = DiagnosticTracker()

def get_signal_funnel_report():
    return diagnostic_tracker.get_report()

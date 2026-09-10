import re

with open('G:/AlgoBot/test_comprehensive_suite.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_test = """
    def test_38_fee_recorded_once(self):
        from capital_manager import CapitalTracker
        tracker = CapitalTracker(500.0)
        # Winning trade
        tracker.record_fee(1.0, event_id="entry_fee_1") # Entry fee
        tracker.record_close(10.0, 1.0, event_id="close_1") # PnL + Exit fee
        
        snap = tracker.get_snapshot()
        self.assertEqual(snap['trading_capital'], 508.0)
        self.assertEqual(snap['total_fees'], 2.0)
        
        # Check idempotency
        tracker.record_fee(1.0, event_id="entry_fee_1")
        tracker.record_close(10.0, 1.0, event_id="close_1")
        self.assertEqual(tracker.get_snapshot()['trading_capital'], 508.0)
        
        # Losing trade
        tracker.record_fee(1.0, event_id="entry_fee_2")
        tracker.record_close(-10.0, 1.0, event_id="close_2")
        snap2 = tracker.get_snapshot()
        self.assertEqual(snap2['trading_capital'], 488.0)
"""

if "test_38_" not in content:
    content = content.replace("    def test_39_", new_test + "\n    def test_39_")
    with open('G:/AlgoBot/test_comprehensive_suite.py', 'w', encoding='utf-8') as f:
        f.write(content)

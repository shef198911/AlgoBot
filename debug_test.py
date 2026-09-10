import unittest
from test_executor_recovery import TestTraderExecutorRecovery

class MyTest(TestTraderExecutorRecovery):
    def test_debug(self):
        try:
            self.test_unknown_amount_fallback_removed()
        except AssertionError as e:
            print("ERROR IN UNKNOWN AMOUNT:")
            print(self.executor.last_error.encode('utf-8'))
            print("AS ASCII:")
            print(self.executor.last_error.encode('ascii', 'backslashreplace'))

if __name__ == '__main__':
    t = MyTest('test_debug')
    t.setUp()
    t.test_debug()
    t.tearDown()

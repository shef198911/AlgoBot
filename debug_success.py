import unittest
from test_executor_recovery import TestTraderExecutorRecovery

class MyTest(TestTraderExecutorRecovery):
    def test_debug(self):
        try:
            self.test_execute_trade_success()
        except AssertionError as e:
            print("ERROR IN SUCCESS TEST:")
            print(self.executor.last_error.encode('utf-8'))

if __name__ == '__main__':
    t = MyTest('test_debug')
    t.setUp()
    t.test_debug()
    t.tearDown()

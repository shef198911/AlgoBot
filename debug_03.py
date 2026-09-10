import unittest
from test_executor import TestExecutor

class MyTest(TestExecutor):
    def test_debug(self):
        try:
            self.test_03_tp_failure_retains_position()
        except AssertionError as e:
            print("ERROR IN SUCCESS TEST:")
            print(repr(self.executor.last_error))
            for call in self.executor.logger.error.call_args_list:
                print("ERROR LOG:", call)
            for call in self.executor.logger.warning.call_args_list:
                print("WARNING LOG:", call)
            for call in self.executor.logger.critical.call_args_list:
                print("CRITICAL LOG:", call)

if __name__ == '__main__':
    t = MyTest('test_debug')
    t.setUp()
    t.test_debug()
    t.tearDown()

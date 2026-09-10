import unittest
from test_comprehensive_suite import TestComprehensiveSuite

class MyTest(TestComprehensiveSuite):
    def test_debug(self):
        try:
            self.test_25_train_ai_end_to_end_mocked()
        except AssertionError as e:
            print("ERROR IN SUCCESS TEST:")
            print(e)

if __name__ == '__main__':
    t = MyTest('test_debug')
    t.test_debug()

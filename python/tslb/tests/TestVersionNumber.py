import unittest

from tslb.VersionNumber import *

class TestVersionNumber(unittest.TestCase):
    def test_comparisons(self):
        # Equality
        self.assertTrue(VersionNumber('0') == VersionNumber('0'))
        self.assertTrue(VersionNumber('1.0') == VersionNumber('1.0'))
        self.assertFalse(VersionNumber('1.0') == VersionNumber('1'))
        self.assertTrue(VersionNumber('1.0a') == VersionNumber('1.0a'))
        self.assertTrue(VersionNumber('1.0.a') == VersionNumber('1.0a'))

        # Inequality
        self.assertFalse(VersionNumber('0') != VersionNumber('0'))
        self.assertFalse(VersionNumber('1.0') != VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0') != VersionNumber('1'))
        self.assertFalse(VersionNumber('1.0a') != VersionNumber('1.0a'))
        self.assertFalse(VersionNumber('1.0.a') != VersionNumber('1.0a'))

        # <=
        self.assertFalse(VersionNumber('1.0') <= VersionNumber('1'))
        self.assertTrue(VersionNumber('1.0') <= VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0') <= VersionNumber('1.1'))
        self.assertTrue(VersionNumber('1.0') <= VersionNumber('2'))

        self.assertFalse(VersionNumber('1.0a') <= VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0a') <= VersionNumber('1.0a'))
        self.assertTrue(VersionNumber('1.0a') <= VersionNumber('1.0b'))
        self.assertTrue(VersionNumber('1.0a') <= VersionNumber('1.0ad'))
        self.assertTrue(VersionNumber('1.0ad') <= VersionNumber('1.0da'))
        self.assertTrue(VersionNumber('1.0a') <= VersionNumber('1.1'))

        # >=
        self.assertFalse(VersionNumber('1') >= VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0') >= VersionNumber('1'))
        self.assertTrue(VersionNumber('1.0') >= VersionNumber('1.0'))
        self.assertFalse(VersionNumber('1.0') >= VersionNumber('1.1'))
        self.assertFalse(VersionNumber('1.0') >= VersionNumber('2'))

        self.assertTrue(VersionNumber('1.0a') >= VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0a') >= VersionNumber('1.0a'))
        self.assertFalse(VersionNumber('1.0a') >= VersionNumber('1.0b'))
        self.assertFalse(VersionNumber('1.0a') >= VersionNumber('1.0ad'))
        self.assertFalse(VersionNumber('1.0ad') >= VersionNumber('1.0da'))
        self.assertFalse(VersionNumber('1.0a') >= VersionNumber('1.1'))

        # <
        self.assertFalse(VersionNumber('1.0') < VersionNumber('1'))
        self.assertFalse(VersionNumber('1.0') < VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0') < VersionNumber('1.1'))
        self.assertTrue(VersionNumber('1.0') < VersionNumber('2'))

        self.assertFalse(VersionNumber('1.0a') < VersionNumber('1.0'))
        self.assertFalse(VersionNumber('1.0a') < VersionNumber('1.0a'))
        self.assertTrue(VersionNumber('1.0a') < VersionNumber('1.0b'))
        self.assertTrue(VersionNumber('1.0a') < VersionNumber('1.0ad'))
        self.assertTrue(VersionNumber('1.0ad') < VersionNumber('1.0da'))
        self.assertTrue(VersionNumber('1.0a') < VersionNumber('1.1'))

        # >
        self.assertFalse(VersionNumber('1') > VersionNumber('1.0'))
        self.assertTrue(VersionNumber('1.0') > VersionNumber('1'))
        self.assertFalse(VersionNumber('1.0') > VersionNumber('1.0'))
        self.assertFalse(VersionNumber('1.0') > VersionNumber('1.1'))
        self.assertFalse(VersionNumber('1.0') > VersionNumber('2'))

        self.assertTrue(VersionNumber('1.0a') > VersionNumber('1.0'))
        self.assertFalse(VersionNumber('1.0a') > VersionNumber('1.0a'))
        self.assertFalse(VersionNumber('1.0a') > VersionNumber('1.0b'))
        self.assertFalse(VersionNumber('1.0a') > VersionNumber('1.0ad'))
        self.assertFalse(VersionNumber('1.0ad') > VersionNumber('1.0da'))
        self.assertTrue(VersionNumber('1.0da') > VersionNumber('1.0ad'))
        self.assertFalse(VersionNumber('1.0a') > VersionNumber('1.1'))

    def test_different_constructors(self):
        # Single int
        self.assertEqual(VersionNumber('0'), VersionNumber(0))

        # Single str
        self.assertEqual(VersionNumber('1.0a').components, [1, 0, 1_000_000_001])
        self.assertEqual(VersionNumber('1.17ad').components, [1, 17, 1_000_000_030])

        # tuple / list
        self.assertEqual(VersionNumber([1,42,'a']), VersionNumber('1.42a'))
        self.assertEqual(VersionNumber(['1',0,'a']), VersionNumber('1.0a'))
        self.assertEqual(VersionNumber([1,'0a']), VersionNumber('1.0a'))

        # Copy
        v1 = VersionNumber('1.0')
        v2 = VersionNumber(v1)

        self.assertEqual(v1.components, v2.components)

    def test_str(self):
        self.assertEqual(str(VersionNumber('1.0')), '1.0')
        self.assertEqual(str(VersionNumber('1.0a')), '1.0.a')
        self.assertEqual(str(VersionNumber('1.0ad')), '1.0.ad')


if __name__ == '__main__':
    unittest.main()

import unittest

from Utils.LoggedDict import LoggedDict


class TestLoggedDict(unittest.TestCase):
    def test_constructor1(self):
        d1 = LoggedDict()

        self.assertEqual(len(d1), 0)

    def test_constructor2(self):
        d1 = LoggedDict(exclusions={'a'})

        with self.assertRaises(KeyError):
            d1['a'] = 3

    def test_setget1(self):
        d1 = LoggedDict(exclusions={'a'})

        d1['b'] = 3
        v1 = d1['b']

        self.assertEqual(v1, 3)
        self.assertEqual(len(d1), 1)

    def test_setget2(self):
        d1 = LoggedDict(exclusions={'a'})

        d1['b'] = 3
        d1['b'] = 4
        v1 = d1['b']
        self.assertEqual(v1, 4)
        self.assertEqual(len(d1), 1)

        lv1 = d1.getValue('b')
        self.assertEqual(len(lv1), 2)

    def test_update1(self):
        data1 = {'a': 3, 'b': 4, 'c': 5}
        data2 = {'a': 4, 'b': 5, 'c': 6}
        d1 = LoggedDict(exclusions={'a'})
        r1 = d1.update(data1)
        self.assertTrue(r1)
        self.assertEqual(d1['b'], 4)
        self.assertEqual(d1['c'], 5)

    def test_update2(self):
        data1 = {'a': 3, 'b': 4, 'c': 5}
        data2 = {'a': 4}
        d1 = LoggedDict(exclusions={'a'})
        d1.update(data1)
        r1 = d1.update(data2)

        self.assertFalse(r1)
        self.assertEqual(d1['b'], 4)
        self.assertEqual(d1['c'], 5)

    def test_purge1(self):
        data1 = {'a': 3, 'b': 4, 'c': 5}
        d1 = LoggedDict(exclusions={'a'})
        d1.update(data1)

        r1 = d1.purge(['c'])
        self.assertTrue(r1)

        with self.assertRaises(ValueError):
            v1 = d1['c']


if __name__ == '__main__':
    unittest.main()

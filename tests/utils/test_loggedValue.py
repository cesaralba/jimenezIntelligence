import unittest

from Utils.LoggedValue import LoggedValue


class Test_LoggedValue(unittest.TestCase):
    def test_constructor1(self):
        v1 = LoggedValue()

        self.assertEqual(len(v1), 0)
        self.assertEqual(v1.get(), None)

    def test_constructor2(self):
        v1 = LoggedValue(5)

        self.assertEqual(len(v1), 1)
        self.assertEqual(v1.get(), 5)

    def test_clear1(self):
        v1 = LoggedValue()
        v1.clear()

        self.assertEqual(len(v1), 1)
        self.assertEqual(v1.deleted, True)
        with self.assertRaises(ValueError):
            v1.get()

    def test_clear2(self):
        v1 = LoggedValue(5)
        v1.clear()

        self.assertEqual(len(v1), 2)
        self.assertEqual(v1.deleted, True)
        with self.assertRaises(ValueError):
            v1.get()

    def test_set1(self):
        v1 = LoggedValue(5)
        r1 = v1.set(4)

        self.assertEqual(len(v1), 2)
        self.assertEqual(v1.get(), 4)
        self.assertEqual(r1, True)

    def test_set2(self):
        v1 = LoggedValue(5)
        r1 = v1.set(5)

        self.assertEqual(len(v1), 1)
        self.assertEqual(v1.get(), 5)
        self.assertEqual(r1, False)

    def test_set3(self):
        v1 = LoggedValue(5)
        v1.clear()
        r1 = v1.set(5)

        self.assertEqual(len(v1), 3)
        self.assertEqual(v1.get(), 5)
        self.assertEqual(r1, True)

    def test_set4(self):
        v1 = LoggedValue(5)
        v1.clear()
        r1 = v1.set(None)

        self.assertEqual(len(v1), 3)
        self.assertEqual(v1.get(), None)
        self.assertEqual(r1, True)

    def test_set5(self):
        v1 = LoggedValue(5)
        v1.clear()
        v1.set(None)
        r1 = v1.set(None)

        self.assertEqual(len(v1), 3)
        self.assertEqual(v1.get(), None)
        self.assertEqual(r1, False)


if __name__ == '__main__':
    unittest.main()

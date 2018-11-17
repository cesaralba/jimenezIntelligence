import unittest

from SMACB.ClasifData import manipulaSocio


class MyTestCase(unittest.TestCase):

    def test_manipulaSocio(self):
        socios = ['as',
                  'asd()',
                  'asdad ()',
                  'sdfsfsf (dfgdgd',
                  'sgsdfg (dfgdgdfg)',
                  'dsfsfsdf (sfsdf) ',
                  ' safsfsdf (dfgsfsfsdf)']

        salidas = ['as',
                   'asd()',
                   'asdad',
                   'sdfsfsf (dfgdgd',
                   'sgsdfg',
                   'dsfsfsdf',
                   'safsfsdf']

        for i, o in zip(socios, salidas):
            self.assertEqual(manipulaSocio(i), o)


if __name__ == '__main__':
    unittest.main()

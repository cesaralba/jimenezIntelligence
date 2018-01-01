'''
Created on Dec 30, 2017

@author: calba
'''

from Utils.Web import ComposeURL, ExtraeGetParams


class TestURLmanagement(object):

    def test_ExtraeGetParams(self):
        urlToTest = "http://acb.com/calendario.php?cod_competicion=SCOPA&cod_edicion=1&vd=1&vh=34"

        urlParameters = ExtraeGetParams(urlToTest)

        assert urlParameters.get('cod_competicion', None) == "SCOPA"
        assert urlParameters.get('cod_edicion', None) == "1"
        assert urlParameters.get('vd', None) == "1"
        assert urlParameters.get('vh', None) == "34"
        assert urlParameters.get('elvis', None) is None

    def test_ComposeURL(self):
        urlToTest = "http://acb.com/calendario.php?cod_competicion=SCOPA&cod_edicion=1&vd=1&vh=34"
        newArgs = {'cod_competicion': "LIGA", 'arg1': "hola"}

        urlComposed = ComposeURL(urlToTest, newArgs)

        urlParameters = ExtraeGetParams(urlComposed)

        assert urlParameters.get('cod_competicion', None) == "LIGA"
        assert urlParameters.get('cod_edicion', None) == "1"
        assert urlParameters.get('vd', None) == "1"
        assert urlParameters.get('vh', None) == "34"
        assert urlParameters.get('arg1', None) == "hola"
        assert urlParameters.get('elvis', None) is None

        urlToTest = "http://acb.com/calendario.php"

        newArgs = dict()
        urlComposed = ComposeURL(urlToTest, newArgs)

        assert urlComposed == urlToTest

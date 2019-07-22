from argparse import Namespace
from time import gmtime
from urllib.parse import (parse_qs, unquote, urlencode, urljoin, urlparse,
                          urlunparse)

from mechanicalsoup import StatefulBrowser


def DescargaPagina(dest, home=None, browser=None, config=Namespace()):
    """
    Descarga el contenido de una pagina y lo devuelve con metadatos
    :param dest: Resultado de un link, URL absoluta o relativa.
    :param home: Situación del browser
    :param browser: Stateful Browser Object
    :param config: Namespace de configuración (de argparse) para manipular ciertas características del browser
    :return: Diccionario con página bajada y metadatos varios
    """
    if browser is None:
        browser = creaBrowser(config)

    if home is None:
        browser.open(dest)
    elif dest.startswith('/'):
        newDest = MergeURL(home, dest)
        browser.open(newDest)
    else:
        browser.open(home)
        browser.follow_link(dest)

    source = browser.get_url()
    content = browser.get_current_page()

    return {'source': source, 'data': content, 'timestamp': gmtime(), 'home': home, 'browser': browser,
            'config': config}


def ExtraeGetParams(url):
    """
       Devuelve un diccionario con los parámetros pasados en la URL
    """

    urlcomps = parse_qs(urlparse(unquote(url)).query)
    result = {}
    for i in urlcomps:
        result[i] = urlcomps[i][0]
    return result


def ComposeURL(url, argsToAdd=None, argsToRemove=[]):
    if not (argsToAdd or argsToRemove):
        return url

    urlGetParams = ExtraeGetParams(url)

    newParams = urlGetParams
    for k in argsToAdd:
        newParams[k] = argsToAdd[k]

    for k in argsToRemove:
        newParams.pop(k)

    urlparams = urlencode(newParams)

    urlcomps = list(urlparse(url=url))
    urlcomps[4] = urlparams
    result = urlunparse(urlcomps)

    return result


def MergeURL(base, link):
    """ Wrapper for urllib.parse.urljoin
    """

    result = urljoin(base, link)

    return result


def creaBrowser(config=Namespace()):
    browser = StatefulBrowser(soup_config={'features': "html.parser"},
                              raise_on_404=True,
                              user_agent="SMparser",
                              )

    if 'verbose' in config:
        browser.set_verbose(config.verbose)

    if 'debug' in config:
        browser.set_debug(config.debug)

    return browser

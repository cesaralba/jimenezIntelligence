import re
from typing import Optional

from CAPcore.Web import createBrowser
from configargparse import Namespace

# https://effbot.org/zone/default-values.htm#what-to-do-instead
sentinel = object()


def getObjID(objURL, clave='id', defaultresult=sentinel):
    PATid = r'^.*/' + clave + r'/(?P<id>\d+)(/.*)?'
    REid = re.match(PATid, objURL)

    if REid:
        return REid.group('id')

    if defaultresult is sentinel:
        raise ValueError(f"getObjID '{objURL}' no casa patrón '{PATid}' para clave '{clave}'")

    return defaultresult


def prepareDownloading(browser, config, urlRef: Optional[str] = None):
    """
    Prepara las variables para el BeautifulSoup si no está y descarga una página si se provee
    :param browser: variable de estado del bs4
    :param config: configuración global del programa (del argparse)
    :param urlRef: página a descargar
    :return: browser,config (los mismos o creados según la situación)
    """
    if config is None:
        config = Namespace()
    else:
        config = Namespace(**config) if isinstance(config, dict) else config
    if browser is None:
        browser = createBrowser(config)
        if urlRef:
            browser.open(urlRef)
    return browser, config

import re
from typing import Optional

from CAPcore.Web import createBrowser, mergeURL
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


def generaURLPlantilla(plantilla, urlRef: str):
    # http://www.acb.com/club/plantilla/id/6/temporada_id/2016
    params = ['/club', 'plantilla', 'id', plantilla.id]
    if plantilla.edicion is not None:
        params += ['temporada_id', plantilla.edicion]

    urlSTR = "/".join(params)

    result = mergeURL(urlRef, urlSTR)

    return result


def generaURLClubes(edicion: Optional[str] = None, urlRef: str = None):
    # https://www.acb.com/club/index/temporada_id/2015
    params = ['/club', 'index']
    if edicion is not None:
        params += ['temporada_id', edicion]

    urlSTR = "/".join(params)

    result = mergeURL(urlRef, urlSTR)

    return result

#TODO: Generar URL jugadores y URL entrenadores

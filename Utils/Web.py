import re
from collections import namedtuple
from re import Pattern
from typing import Optional

import bs4.element
from CAPcore.Web import createBrowser, mergeURL
from configargparse import Namespace

# https://effbot.org/zone/default-values.htm#what-to-do-instead
sentinel = object()

browserConfigData = namedtuple('browserConfigData', field_names=['config', 'browser', 'timestamp'],
                               defaults=[None, None])


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
    # https://www.acb.com/club/plantilla/id/6/temporada_id/2016
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


def generaURLEstadsPartido(partidoId, urlRef: str = None):
    # https://www.acb.com/partido/estadisticas/id/104476
    params = ['/partido', 'estadisticas', 'id', str(partidoId)]

    urlSTR = "/".join(params)

    result = mergeURL(urlRef, urlSTR)

    return result


# TODO: Generar URL jugadores y URL entrenadores

def tagAttrHasValue(tagData: bs4.element.Tag, attrName: str, value: str | Pattern, partial: bool = False) -> bool:
    if tagData is None:
        return False

    if attrName not in tagData.attrs:
        return False

    attrValue = tagData[attrName]

    if isinstance(attrValue, str):
        if isinstance(value, Pattern):
            if re.match(value, attrValue):
                return True
            return False
        if partial:
            return value in attrValue
        return value == attrValue
    for auxVal in attrValue:
        if isinstance(value, Pattern):
            if re.match(value, auxVal):
                return True
            continue
        if partial:
            if value in attrValue:
                return True
            continue
        if value == attrValue:
            return True
    return False

import ast
import logging
import re
from collections import namedtuple
from pprint import pp
from re import Pattern
from typing import Optional, Dict, Any

import bs4.element
import json5
from CAPcore.Misc import listize
from CAPcore.Web import createBrowser, mergeURL, DownloadedPage
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
    attrValueList = listize(attrValue)

    for auxVal in attrValueList:
        if isinstance(value, Pattern):
            if re.match(value, auxVal):
                return True
            continue
        if partial:
            if value in attrValueList:
                return True
            continue
        if value == attrValueList:
            return True
    return False


logger = logging.getLogger()


def extractPagDataScripts(calPage: DownloadedPage, keyword=None) -> Optional[Dict[str,Any]]:
    patWrapper = r'^self\.__next_f\.push\((.*)\)$'

    calData = calPage.data

    auxList = []

    for scr in calData.find_all('script'):
        scrText = scr.text
        if keyword and keyword not in scrText:
            continue
        reWrapper = re.match(patWrapper, scrText)
        if reWrapper is None:
            continue

        wrappedText = reWrapper.group(1)

        try:
            firstEval = ast.literal_eval(wrappedText)
        except SyntaxError:
            logging.exception("No scanea Eval: %s", scr.prettify())
            continue

        patForcedict = r"^\s*([^:]+)\s*:\s*(.*)\s*$"
        reForceDict = re.match(patForcedict, firstEval[1])

        if reForceDict is None:
            logger.error("No casa RE '%s' : %s", reForceDict, scr.prettify())
            continue
        dictForced = "{" + f'"{reForceDict.group(1)}":{reForceDict.group(2)}' + "}"
        try:
            jsonParsed = json5.loads(dictForced)
        except Exception:
            logging.exception("No scanea json: %s", scr.prettify())
            continue

        auxList.append(jsonParsed)

    result = {}

    for data in auxList:
        auxHash={}
        auxHash.update(data)

        if list(auxHash.keys())[0] in result:
            clave=list(auxHash.keys())[0]
            print(f"Clave #{clave}# ya existe en resultado:\n")
            pp(result[clave])
            print("==================")
            continue
        result.update(auxHash)

    return result

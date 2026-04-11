import ast
import logging
import re
from collections import namedtuple
from copy import copy
from pprint import pprint
from re import Pattern
from typing import Optional, Dict, Any, List
from urllib.parse import urlsplit, ParseResult, urlparse, parse_qs, urlunparse, urlencode

import bs4.element
import json5
from CAPcore.Misc import listize
from CAPcore.Web import createBrowser, mergeURL, DownloadedPage
from configargparse import Namespace
from unidecode import unidecode

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


def getIDfromEncURL(objURL, defaultresult=sentinel, suf2ignore=sentinel):
    if suf2ignore is sentinel:
        suf2ignore = {}
    partsURLpath = urlsplit(url=objURL).path.split('/')

    comp2treat = getLastUsefulComp(partsURLpath, suf2ignore)

    if comp2treat:
        result = comp2treat.split('-')[-1]
        return result

    if defaultresult is sentinel:
        excStr = f" Excl: {','.join(sorted(map(lambda s: f"'{s}'", suf2ignore)))}" if suf2ignore else ""
        raise ValueError(f"getObjID '{objURL}' no tiene path util.{excStr}")

    return defaultresult


def getLastUsefulComp(compList: List[str], suf2ignore=sentinel) -> Optional[str]:
    if not compList:
        return None

    if suf2ignore is sentinel:
        return compList[-1]

    for comp in reversed(compList):
        if comp not in suf2ignore:
            return comp

    return None


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


def extractPagDataScripts(calPage: DownloadedPage, keyword=None) -> Optional[Dict[str, Any]]:
    patWrapper = r'^self\.__next_f\.push\((.*)\)$'

    auxList = []

    for scr in calPage.data.find_all('script'):
        if keyword and keyword not in scr.text:
            continue
        reWrapper = re.match(patWrapper, scr.text)
        if reWrapper is None:
            continue

        try:
            firstEval = ast.literal_eval(reWrapper.group(1))
        except SyntaxError:
            logger.exception("No scanea Eval: %s", scr.prettify())
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
            logger.exception("No scanea json: %s", scr.prettify())
            continue

        auxList.append(jsonParsed)

    result = {}

    for data in auxList:
        auxHash = {}
        auxHash.update(data)

        if list(auxHash.keys())[0] in result:
            clave = list(auxHash.keys())[0]
            logging.error("Clave #%s# ya existe en resultado:\n%s", clave, pprint(result[clave]))
            continue
        result.update(auxHash)

    return result


def generaCompParaURL(nombreEnt: str, idEnt: str):
    auxList = re.split(r'\s+', nombreEnt.strip())
    auxList.append(idEnt)
    # https://stackoverflow.com/a/19769972
    # https://pypi.org/project/Unidecode/
    result = unidecode('-'.join(auxList)).lower()

    return result


def generaURLACB(urlComps: List[str], urlRef: str, urlParams: Optional[Dict[str, str]] = None):
    auxParams: dict[Any, Any] = {} if (urlParams is None) else urlParams

    urlPath = "/".join(urlComps)
    compsCurr: ParseResult = urlparse(urlRef)
    infoParams = parse_qs(compsCurr.query)
    desiredParams = copy(infoParams)
    desiredParams.update(auxParams)
    result = urlunparse(
        ParseResult(scheme=compsCurr.scheme, netloc=compsCurr.netloc, path=urlPath, params=compsCurr.params,
                    query=urlencode(desiredParams), fragment=compsCurr.fragment))

    return result

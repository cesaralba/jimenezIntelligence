import ast
import logging
import re
from collections import namedtuple
from copy import copy
from re import Pattern
from typing import Optional, Dict, Any, List, AnyStr
from urllib.parse import urlsplit, ParseResult, urlparse, parse_qs, urlunparse, urlencode

import bs4.element
import json5
from CAPcore.Misc import listize
from CAPcore.Web import createBrowser, mergeURL, DownloadedPage
from configargparse import Namespace
from mechanicalsoup import StatefulBrowser
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
        excStr = f" Excl: {','.join(sorted(f"'{s}'" for s in suf2ignore))}" if suf2ignore else ""
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


def prepareDownloading(browser: Optional[StatefulBrowser] = None, config: Optional[Namespace | Dict] = None):
    """
    Prepara las variables para el BeautifulSoup si no está y descarga una página si se provee
    :param browser: variable de estado del bs4
    :param config: configuración global del programa (del argparse)
    :return: browser,config (los mismos o creados según la situación)
    """

    if config is None:
        config = Namespace()
    else:
        config = Namespace(**config) if isinstance(config, dict) else config
    if browser is None:
        browser = createBrowser(config)
    return browser, config


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


def keyWordNotPresent(data: str, keyword: Optional[str]) -> bool:
    result = (keyword is not None) and (keyword not in data)
    return result


REpatSplitter = r'([a-z0-9]{0,2}):((Te.*\.)|((\[.*\]\n)|(I\[.*\])\n))'


def extraePagDataScripts(calPage: DownloadedPage, keyword=None) -> Optional[Dict[str, Any]]:
    result = {}

    patWrapper = r'^self\.__next_f\.push\((.*)\)$'

    for scr in calPage.data.find_all('script'):
        if keyWordNotPresent(scr.text, keyword):
            continue
        reWrapper = re.match(patWrapper, scr.text)
        if reWrapper is None:
            continue

        try:
            firstEval = ast.literal_eval(reWrapper.group(1))
        except SyntaxError:
            logger.exception("No scanea Eval: %s", scr.prettify())
            continue

        for d1 in re.findall(REpatSplitter, firstEval[1]):
            clave, valor, *ignore = d1
            if keyWordNotPresent(valor, keyword):
                continue

            if valor[0] in ('I', '"', 'C', 'X'):
                continue

            if clave in result:
                logger.exception("Clave '%s' ya en resultado", clave)
                continue

            try:
                jsonParsed = json5.loads(valor)
            except Exception:
                logger.exception("Clave '%s' no scanea json", clave)
                print("CAP **********************************")
                print(valor)
                print("CAP ----------------------------------")
                print(reWrapper.group(1))
                print("CAP **********************************")
                # return firstEval[1]

                continue

            result[clave] = jsonParsed

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


# Esto debe ir a CAPCORE
def generaURLhijo(urlRef: str, cadHijo: AnyStr) -> AnyStr:
    if cadHijo.startswith('/'):
        return mergeURL(urlRef, cadHijo)

    compsCurr: ParseResult = urlparse(urlRef)
    currPath = compsCurr.path.split('/')
    currPath.append(cadHijo)

    urlPath = "/".join(currPath)
    result = urlunparse(
        ParseResult(scheme=compsCurr.scheme, netloc=compsCurr.netloc, path=urlPath, params=compsCurr.params,
                    query=compsCurr.query, fragment=compsCurr.fragment))

    return result

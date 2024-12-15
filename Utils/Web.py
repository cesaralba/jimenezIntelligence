import re

from CAPcore.Web import mergeURL

from SMACB.Constants import URL_BASE

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


def generaURLPlantilla(plantilla):
    # http://www.acb.com/club/plantilla/id/6/temporada_id/2016
    params = ['/club', 'plantilla', 'id', plantilla.id]
    if plantilla.edicion is not None:
        params += ['temporada_id', plantilla.edicion]

    urlSTR = "/".join(params)

    result = mergeURL(URL_BASE, urlSTR)

    return result


def generaURLClubes(edicion=None):
    # https://www.acb.com/club/index/temporada_id/2015
    params = ['/club', 'index']
    if edicion is not None:
        params += ['temporada_id', edicion]

    urlSTR = "/".join(params)

    result = mergeURL(URL_BASE, urlSTR)

    return result

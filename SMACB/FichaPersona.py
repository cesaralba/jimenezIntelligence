import logging
from collections import namedtuple
from typing import Optional, Set, List

import bs4
from CAPcore.Web import mergeURL, DownloadedPage, downloadPage

from SMACB.Constants import URL_BASE, URLIMG2IGNORE
from Utils.Misc import sortedByStringLength
from Utils.ParseoData import procesaCosasUtilesPlantilla, findLocucionNombre
from Utils.Web import prepareDownloading, getObjID

VALIDTYPES = {'jugador', 'entrenador'}

TempClubInfoBasic = namedtuple('TempClubInfoBasic', ['tempId', 'clubId', 'clubName'])
TempClubInfo = namedtuple('TempClubInfo', ['tempId', 'tempName', 'clubId', 'clubName'])


class EstanciaClub:
    def __init__(self, **kwargs):
        self.tempIni: Optional[str] = None
        self.tempFin: Optional[str] = None
        self.numTemps: int = 0
        self.clubId: Optional[str] = None
        self.clubNames: Set[str] = set()

        ClavesValidasEstancia = {'tempIni', 'tempFin', 'clubId', 'numTemps', 'clubName'}
        badKeys = set(kwargs.keys()).difference(ClavesValidasEstancia)
        if badKeys:
            raise ValueError(
                f"EstanciaClub: sobran claves: {badKeys}. Esperadas: {ClavesValidasEstancia}. Datos: {kwargs}")
        missingKeys = ClavesValidasEstancia.difference(kwargs.keys())
        if missingKeys:
            raise ValueError(
                f"EstanciaClub: faltan claves: {missingKeys}. Esperadas: {ClavesValidasEstancia}. Datos: {kwargs}")

        for k, v in kwargs.items():
            if k == 'clubName':
                self.clubNames.add(v)
                continue
            setattr(self, k, v)

    def esClub(self, clubId: str) -> bool:
        return self.clubId == clubId

    def esSigTemp(self, tempId: str):
        return int(self.tempFin) + 1 == int(tempId)

    @classmethod
    def fromTempClubInfo(cls, data: TempClubInfo):
        if not isinstance(data, TempClubInfo):
            raise TypeError(f"EstanciaClub.fromTempClubInfo espera datos de tipo TempClubInfo. Recibido {type(data)}")

        sourceData = {'tempIni': data.tempId, 'tempFin': data.tempId, 'clubId': data.clubId, 'numTemps': 1,
                      'clubName': data.clubName}
        result = cls(**sourceData)
        result.clubNames.add(data.clubName)

        return result

    def __add__(self, other: TempClubInfo):
        if not isinstance(other, TempClubInfo):
            raise TypeError(f"EstanciaClub.__add__ espera datos de tipo TempClubInfo. Recibido {type(other)}")
        if not (self.esClub(other.clubId) and self.esSigTemp(other.tempId)):
            raise ValueError(
                f"EstanciaClub.__add__ Solo puede añadir al mismo club {self.clubId} y la siguiente temporada a "
                f"{self.tempFin}. Recibido club '{other.clubId}' y temp '{other.tempId}")
        self.tempFin = other.tempId
        self.numTemps += 1
        self.clubNames.add(other.clubName)

        return self

    def __str__(self):
        if self.numTemps == 0:
            return "null"

        targetName = sortedByStringLength(self.clubNames)[0]
        priYear = self.tempIni
        ultYear = (int(self.tempFin) + 1) % 100
        return f"{priYear}-{ultYear:02} ({self.numTemps} temps) [{self.clubId}] {targetName}"

    __repr__ = __str__


class FichaPersona:
    def __init__(self, **kwargs):
        changesInfo = {'NuevoJugador': True}
        self.timestamp = kwargs.get('timestamp', None)

        if 'id' not in kwargs:
            raise ValueError(f"Jugador nuevo sin 'id': {kwargs}")
        self.id = kwargs.get('id', None)
        self.URL = kwargs.get('URL', None)
        self.audioURL = kwargs.get('audioURL', None)
        self.tipoFicha: Optional[str] = None
        self.sinDatos: Optional[bool] = None

        self.nombre = kwargs.get('nombre', None)
        self.alias = kwargs.get('alias', self.nombre)
        self.lugarNac = kwargs.get('lugarNac', None)
        self.fechaNac = kwargs.get('fechaNac', None)
        self.nacionalidad = kwargs.get('nacionalidad', None)

        self.nombresConocidos = set()
        self.urlConocidas = set()
        self.fotos = set()

        self.ultClub = None

        self.primPartidoP = None
        self.ultPartidoP = None
        self.primPartidoT = None
        self.ultPartidoT = None
        self.partidos = set()
        self.equipos = set()

        if self.nombre is not None:
            self.nombresConocidos.add(self.nombre)
        if self.alias is not None:
            self.nombresConocidos.add(self.alias)

        if self.URL is not None:
            self.urlConocidas.add(self.URL)

        self.updateFoto(urlFoto=kwargs.get('urlFoto', None), urlBase=self.URL, changeDict=changesInfo)

        ultClub = kwargs.get('club', None)
        if ultClub is not None:
            self.equipos.add(ultClub)
            self.ultClub = ultClub

    def buildURL(self):
        if self.tipoFicha is None:
            raise ValueError("buildURL: type of data unset")
        if self.tipoFicha not in VALIDTYPES:
            raise ValueError(f"buildURL: unknown type of data. Valid ones: {', '.join(sorted(VALIDTYPES))}")

        newPathList = ['', self.tipoFicha, 'temporada-a-temporada', 'id', self.id]
        newPath = '/'.join(newPathList)

        result = mergeURL(URL_BASE, newPath)

        return result

    def updateFoto(self, urlFoto: Optional[str], urlBase: Optional[str], changeDict: Optional[dict] = None):
        changes = False

        if urlFoto is not None and urlFoto not in URLIMG2IGNORE:
            changes = True
            newURL = mergeURL(urlBase, urlFoto)
            self.fotos.add(newURL)
            if changeDict:
                changeDict['urlFoto'] = ("", "Nueva")
        return changes


def descargaPagina(datos, home=None, browser=None, config=None) -> Optional[DownloadedPage]:
    browser, config = prepareDownloading(browser, config)

    url = datos.buildURL()

    logging.info("Descargando ficha de %s '%s'", datos.tipoFicha, url)
    try:
        result: DownloadedPage = downloadPage(url, home=home, browser=browser, config=config)
    except Exception as exc:
        result = None
        logging.error("Problemas descargando '%s'", url)
        logging.exception(exc)

    return result


def extraeDatosPersonales(datosPag: Optional[DownloadedPage], datosPartido: Optional[dict] = None):
    auxResult = {}

    if datosPartido is not None:
        auxResult['sinDatos'] = True
        auxResult['alias'] = datosPartido['nombre']

    if datosPag is None:
        return auxResult

    auxResult['URL'] = datosPag.source
    auxResult['timestamp'] = datosPag.timestamp

    fichaData: bs4.BeautifulSoup = datosPag.data

    cosasUtiles: Optional[bs4.BeautifulSoup] = fichaData.find(name='div', attrs={'class': 'datos'})

    if cosasUtiles is not None:
        auxResult.update(procesaCosasUtilesPlantilla(data=cosasUtiles, urlRef=auxResult['URL']))

    auxResult.update(findLocucionNombre(data=fichaData))

    return auxResult


def extraeTrayectoria(datosPag: Optional[DownloadedPage]) -> Optional[List[TempClubInfo]]:
    result = []
    fichaData: bs4.BeautifulSoup = datosPag.data

    intSection = fichaData.find('section', attrs={'class': 'contenedora_temporadas'})
    if intSection is None:
        return None
    tabla = intSection.find('table', attrs={'class': 'roboto'})

    for fila in tabla.findAll('tr'):
        if 'totales' in fila.get('class', set()):
            continue
        celdaTemp = fila.find('td', attrs={'class': 'temporada'})
        if celdaTemp is None:
            continue
        celdaClub = fila.find('td', attrs={'class': 'nombre'})
        if celdaClub is None:
            continue
        auxTemp = extractTempClubInfo(celdaClub.find('a'))._asdict()
        auxTemp.update({'tempName': celdaTemp.getText()})
        result.append(TempClubInfo(**auxTemp))

    return result


def extractTempClubInfo(datos: bs4.element.Tag) -> TempClubInfoBasic:
    if datos.name != 'a':
        raise TypeError(f"extractTempClubInfo: expected tag 'a', got '{datos.name}'. Source: {datos}")

    destURL = datos['href']
    clubId = getObjID(destURL, 'id')
    tempId = getObjID(destURL, clave='temporada_id')
    clubName = datos.getText()

    return TempClubInfoBasic(tempId=tempId, clubId=clubId, clubName=clubName)


def construyeEstanciaList(data: List[TempClubInfo]):
    result = []
    currClub = None

    for tempInfo in data:
        if currClub is None:
            currClub = EstanciaClub.fromTempClubInfo(tempInfo)
            result.append(currClub)
            continue
        if currClub.esClub(tempInfo.clubId) and currClub.esSigTemp(tempInfo.tempId):
            currClub = currClub + tempInfo
        else:
            currClub = EstanciaClub.fromTempClubInfo(tempInfo)
            result.append(currClub)
    return result

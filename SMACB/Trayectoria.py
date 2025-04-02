from collections import namedtuple, defaultdict
from typing import Optional, Set, List, Dict

import bs4
from CAPcore.Web import DownloadedPage

from Utils.Misc import sortedByStringLength
from Utils.Web import getObjID

TempClubInfoBasic = namedtuple('TempClubInfoBasic', ['tempId', 'clubId', 'clubName'])
TempClubInfo = namedtuple('TempClubInfo', ['tempId', 'tempName', 'clubId', 'clubName'])
ResEstanciasTray = namedtuple('ResEstanciasTray', ['clubId', 'numTemps', 'numPeriods', 'periodos'])
EstanciaClubData = namedtuple('EstanciaClubData', ['numTemps', 'numPeriods', 'ultPeriodo'])


class Trayectoria:
    def __init__(self, trayectoria: List[TempClubInfo]):
        self.trayectoria: List[EstanciaClub] = construyeEstanciaList(trayectoria)

    def tempsACB(self):
        auxSet = set()
        for est in self.trayectoria:
            auxSet.update(est.tempIDs)
        result = len(auxSet)
        return result

    def tempsEnClub(self, ultimoPeriodo: bool = True) -> [int, EstanciaClubData]:
        """
        :param ultimoPeriodo:
        :return:
        """
        ultEst = self.trayectoria[-1]
        if ultimoPeriodo:
            return ultEst.numTemps
        resEstancias = self.resumenTrayectoria()[ultEst.clubId]
        return (EstanciaClubData(**{'numTemps': resEstancias.numTemps, 'numPeriods': resEstancias.numPeriods,
                                    'ultPeriodo': ultEst.numTemps}))

    def resumenTrayectoria(self) -> Dict[str, ResEstanciasTray]:
        auxTrayect = defaultdict(lambda: {'clubId': None, 'numTemps': 0, 'numPeriods': 0, 'periodos': []})

        for est in self.trayectoria:
            auxTrayect[est.clubId]['clubId'] = est.clubId
            auxTrayect[est.clubId]['numTemps'] += est.numTemps
            auxTrayect[est.clubId]['numPeriods'] += 1
            auxTrayect[est.clubId]['periodos'].append(est.buildPeriodoStr())

        result = {k: ResEstanciasTray(**v) for k, v in auxTrayect.items()}

        return result

    @classmethod
    def fromWebPage(cls, data: DownloadedPage):
        datosTrayectoria = extraeTrayectoria(data)

        if datosTrayectoria is None:
            return None

        return cls(datosTrayectoria)


class EstanciaClub:
    def __init__(self, **kwargs):
        self.tempIni: Optional[str] = None
        self.tempFin: Optional[str] = None
        self.numTemps: int = 0
        self.clubId: Optional[str] = None
        self.clubNames: Set[str] = set()
        self.tempIDs: Set[str] = set()

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
        self.tempIDs.add(kwargs['tempFin'])

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
        self.tempIDs.add(other.tempId)

        return self

    def buildPeriodoStr(self) -> str:
        priYear = self.tempIni
        ultYear = (int(self.tempFin) + 1) % 100

        result = f"{priYear}-{ultYear:02}"

        return result

    def __str__(self):
        if self.numTemps == 0:
            return "null"

        tempsTag = f"({self.numTemps} temp{'s' if self.numTemps > 1 else ''})"
        targetName = sortedByStringLength(self.clubNames)[0]
        return f"{self.buildPeriodoStr()} {tempsTag} [{self.clubId}] {targetName}"

    __repr__ = __str__


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

import logging
from time import gmtime
from typing import Optional, Set, Dict, Any, Tuple

import bs4
from CAPcore.LoggedValue import LoggedValue
from CAPcore.Misc import copyDictWithTranslation
from CAPcore.Web import mergeURL, DownloadedPage, downloadPage
from pandas import Timestamp

from Utils.ParseoData import procesaCosasUtilesPlantilla, findLocucionNombre
from Utils.Web import prepareDownloading, getObjID, sentinel
from .Constants import URL_BASE, URLIMG2IGNORE, CLAVESFICHAPERSONA
from .PartidoACB import PartidoACB
from .Trayectoria import Trayectoria

VALIDPERSONATYPES = {'jugador', 'entrenador'}

PERSONABASICTAGS = {'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', }


class FichaPersona:
    def __init__(self, changesInfo=sentinel, **kwargs):
        if changesInfo is sentinel:
            changesInfo = {}

        self.timestamp = kwargs.get('timestamp', gmtime())

        if 'id' not in kwargs:
            raise ValueError(f"Ficha nueva sin 'persID': {kwargs}")
        self.persID: str = kwargs['id']
        self.sinDatos: Optional[bool] = None
        tipoPers: Optional[str] = kwargs.get('tipoFicha', None)
        if tipoPers not in VALIDPERSONATYPES:
            raise ValueError(f"Persona Id '{self.persID}' Tipo '{tipoPers}' no válido. Aceptados: {VALIDPERSONATYPES}")
        self.tipoFicha: Optional[str] = tipoPers
        self.URL: Optional[str] = None
        self.trayectoria: Optional[Trayectoria] = None

        self.audioURL: Optional[str] = None
        self.nombre: Optional[str] = None
        self.alias: Optional[str] = None
        self.lugarNac: Optional[str] = None
        self.fechaNac: Optional[str] = None
        self.nacionalidad: Optional[str] = None
        self.nombresConocidos: Set[str] = set()
        self.fotos: Set[str] = set()
        self.urlConocidas: Set[str] = set()

        self.ultClub: Optional[str] = None

        self.partsTemporada: PartidosClub = PartidosClub(persID=self.persID, tipoFicha=self.tipoFicha, clubId=None)
        self.partsClub: Dict[str, PartidosClub] = {}

        self.primPartidoP: Optional[str] = None
        self.ultPartidoP: Optional[str] = None
        self.primPartidoT: Optional[str] = None
        self.ultPartidoT: Optional[str] = None
        self.partidos: Set[str] = set()
        self.equipos: Set[str] = set()

        self.actualizaBioBasic(changeInfo=changesInfo, **kwargs)

    def actualizaBio(self, changeInfo=sentinel, **kwargs):
        raise NotImplementedError("actualizaBio tiene que estar en las clases derivadas")

    def actualizaBioBasic(self, changeInfo=sentinel, **kwargs) -> bool:

        if changeInfo is sentinel:
            changeInfo = {}
        result = False
        for k in CLAVESFICHAPERSONA:
            if k not in kwargs:
                continue
            if getattr(self, k) != kwargs[k]:
                result |= True
                oldV = getattr(self, k)
                setattr(self, k, kwargs[k])
                changeInfo[k] = (oldV, kwargs[k])

        if self.nombre is not None and self.nombre not in self.nombresConocidos:
            result |= True
            self.nombresConocidos.add(self.nombre)

        if self.alias is not None and self.alias not in self.nombresConocidos:
            result |= True
            self.nombresConocidos.add(self.alias)

        result |= self.updateFoto(urlFoto=kwargs.get('urlFoto', None), urlBase=self.URL, changeDict=changeInfo)

        ultClub = kwargs.get('club', None)
        if ultClub is not None:
            self.equipos.add(ultClub)
            self.ultClub = ultClub
            changeInfo['club'] = (None, ultClub)
            result |= True

        return result

    def buildURL(self):
        if self.tipoFicha is None:
            raise ValueError("buildURL: type of data unset")
        if self.tipoFicha not in VALIDPERSONATYPES:
            raise ValueError(f"buildURL: unknown type of data. Valid ones: {', '.join(sorted(VALIDPERSONATYPES))}")

        newPathList = ['', self.tipoFicha, 'temporada-a-temporada', 'id', self.persID]
        newPath = '/'.join(newPathList)

        result = mergeURL(URL_BASE, newPath)

        return result

    def infoFichaStr(self) -> Tuple[str, str]:
        raise NotImplementedError("infoFichaStr tiene que estar en las clases derivadas")

    def nombreFicha(self):
        nombreStr = self.alias or self.nombre
        fechaNacStr = "Sin datos" if self.fechaNac is None else self.fechaNac.strftime('%Y-%m-%d')
        gamesStr = "Sin partidos registrados" if self.primPartidoT is None else (
            f"Parts:[{len(self.partidos)}] {self.primPartidoT.strftime('%Y-%m-%d')} -> "
            f"{self.ultPartidoT.strftime('%Y-%m-%d')}")
        prefPers, datosPers = self.infoFichaStr()
        eqPlural = "s" if len(self.equipos) != 1 else ""

        return (f"{prefPers}: {nombreStr} ({self.persID}) {fechaNacStr} {datosPers} "
                f"({len(self.equipos)} eq{eqPlural}) {gamesStr}")

    __repr__ = nombreFicha
    __str__ = nombreFicha

    def updateFoto(self, urlFoto: Optional[str], urlBase: Optional[str], changeDict: Optional[dict] = None):
        changes = False

        if urlFoto is not None and urlFoto not in URLIMG2IGNORE:
            changes = True
            newURL = mergeURL(urlBase, urlFoto)
            self.fotos.add(newURL)
            if changeDict:
                changeDict['urlFoto'] = ("", "Nueva")
        return changes

    def descargaPagina(self, home=None, browser=None, config=None) -> Optional[DownloadedPage]:
        browser, config = prepareDownloading(browser, config)

        url = self.buildURL()

        logging.info("Descargando ficha de %s '%s'", self.tipoFicha, url)
        try:
            result: DownloadedPage = downloadPage(url, home=home, browser=browser, config=config)
        except Exception as exc:
            result = None
            logging.error("Problemas descargando '%s'", url)
            logging.exception(exc)

        return result

    @classmethod
    def fromURL(cls, url: str, datos: Optional[dict] = None, home=None, browser=None, config=None):

        persId = getObjID(url, 'ver', None)
        if persId is None:
            raise ValueError(f"FichaPersona.fromURL: incapaz de sacar ID de f'{url}'. Buscados 'ver' e 'persID'")
        newData = {'persID': persId}
        if datos is not None:
            newData.update(datos)

        result = cls(**newData)
        result.actualizaDatosWeb(browser, config, home)

        return result

    @classmethod
    def fromPartido(cls, idJugador: str, datosPartido: Optional[dict] = None, **kwargs):
        """
        Crear una ficha de jugador a partir de los datos del partido. Bien porque no se descarguen fichas,
        bien como fallback
        :param idJugador: Código del jugador
        :param datosPartido: Info del partido (de PartidoACB.Jugadores
        :param kwargs: parámetros que no vienen en datosPartido (timestamp)
        :return: Nuevo objeto creado
        """
        TRFICHAJUG = {'IDequipo': 'club', 'codigo': 'id', 'nombres': 'alias'}
        EXFICHAJUG = {'competicion', 'temporada', 'jornada', 'equipo', 'CODequipo', 'rival', 'CODrival', 'IDrival',
                      'url', 'estado', 'esLocal', 'haGanado', 'estads', 'esJugador', 'entrenador', 'haJugado', 'dorsal',
                      'esTitular', 'linkPersona', }

        if datosPartido is None:
            datosPartido = {}

        fichaJug = {'id': idJugador}
        if 'linkPersona' in datosPartido:
            fichaJug['URL'] = mergeURL(URL_BASE, datosPartido['linkPersona'])
        fichaJug.update(kwargs)

        auxDatosPartido = copyDictWithTranslation(source=datosPartido, translation=TRFICHAJUG, excludes=EXFICHAJUG)
        fichaJug.update(auxDatosPartido)

        return cls(**fichaJug)

    def ficha2dict(self) -> Dict[str, str]:
        result = {k: getattr(self, k) for k in PERSONABASICTAGS}
        return result

    def nuevoPartido(self, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """
        result = False

        dicTipo = partido.Jugadores if self.tipoFicha == 'jugador' else partido.Entrenadores

        if self.persID not in dicTipo:
            raise ValueError(
                f"{self.tipoFicha.capitalize()}: '{self.nombre}' ({self.persID}) no ha jugado partido {partido.url}")

        datosPersPart = dicTipo[self.persID]
        eqPersona = datosPersPart['IDequipo']

        result |= self.partsTemporada.addPartido(persona=self, partido=partido)

        if eqPersona not in self.partsClub:
            self.partsClub[eqPersona] = PartidosClub(persID=self.persID, tipoFicha=self.tipoFicha, clubId=eqPersona)
            result = True

        result |= self.partsClub[eqPersona].addPartido(persona=self, partido=partido)

        return result

    def actualizaDatosWeb(self, browser=None, config=None, home=None) -> bool:
        result = False
        pag = self.descargaPagina(home, browser, config)
        if pag is None:
            return False
        datosPersona = extraeDatosPersonales(datosPag=pag)
        result |= self.actualizaBio(datosPersona)
        if self.trayectoria is None:
            self.trayectoria = Trayectoria.fromWebPage(data=pag)
            result |= True

        return result


class PartidosClub:
    def __init__(self, persID: str, tipoFicha: str, clubId: Optional[str]):
        self.persID: str = persID
        self.tipoFicha: str = tipoFicha
        self.clubID: Optional[str] = clubId
        self.equipos: Set[str] = set()

        self.primPartidoP: Optional[str] = None
        self.ultPartidoP: Optional[str] = None
        self.primPartidoT: Optional[str] = None
        self.ultPartidoT: Optional[str] = None
        self.partidos: Set[str] = set()

    def addPartido(self, persona: FichaPersona, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """

        dicTipo = partido.Jugadores if persona.tipoFicha == 'jugador' else partido.Entrenadores

        if self.persID not in dicTipo:
            raise ValueError(
                f"{persona.tipoFicha.capitalize()}: '{persona.nombre}' ({self.persID}) no ha jugado partido "
                f"{partido.url}")

        if partido.url in self.partidos:
            return False

        datosPersPart = dicTipo[self.persID]
        eqJugador = datosPersPart['IDequipo']
        if self.clubID is None:
            self.equipos.add(eqJugador)
        else:
            if eqJugador != self.clubID:
                raise ValueError(
                    f"{persona.tipoFicha.capitalize()}: '{persona.nombre}' ({self.persID}) Añadiendo {partido.url} a "
                    f"registro incorrecto. Registro: '{self.clubID}'. Partido: '{eqJugador}'")

        self.partidos.add(partido.url)

        if persona.ultClub is None:
            persona.ultClub = datosPersPart['IDequipo']

        if (self.primPartidoT is None) or (partido.fechaPartido < self.primPartidoT):
            self.primPartidoP = partido.url
            self.primPartidoT = partido.fechaPartido

        if (self.ultPartidoT is None) or (partido.fechaPartido > self.ultPartidoT):
            self.ultPartidoP = partido.url
            self.ultPartidoT = partido.fechaPartido
        return True


EXCLUDEFICHACLUBPERSONA = ['persId', 'clubId']


class FichaClubPersona:
    def __init__(self, **kwargs):
        changesInfo = kwargs.get('changesInfo', {})

        self.persId: Optional[str] = None
        self.clubId: Optional[str] = None
        self.alta: Optional[Timestamp] = None
        self.baja: Optional[Timestamp] = None
        self.activo: Optional[bool] = None

        for k, v in kwargs.items():
            if hasattr(self, k):
                currVal = getattr(self, k)
                currVal.set(v)
                setattr(self, k, currVal)

        if self.alta is None:
            self.alta = gmtime()

    def update(self, **kwargs):
        changesInfo = kwargs.get('changesInfo', {})

        if not self.checkPersonId(**kwargs):
            objK = {k: self.__dict__.get(k) for k in EXCLUDEFICHACLUBPERSONA}
            newK = {k: kwargs.get(k) for k in EXCLUDEFICHACLUBPERSONA}

            raise KeyError(f"Actualización de la persona incorrecta. Actual: {objK}. Datos: {newK}")

        changesInfo.update(getLoggedDiff(self, kwargs))

        for k, (_, vNew) in changesInfo.items():
            getattr(self, k).set(vNew)

        return changesInfo

    def checkPersonId(self, **kwargs):

        return all(getattr(self, k) == kwargs.get(k, None) for k in EXCLUDEFICHACLUBPERSONA)

    def getCurrentData(self):
        result = {k: v.get() for k,v in self.__dict__.items() if isinstance(v, LoggedValue)}

        return result


def getLoggedDiff(obj: object, newData: Dict[str, Any]) -> Dict[str, Tuple[Any, Any]]:
    result = {}
    for k, v in newData.items():
        if hasattr(obj, k):
            auxObjV = getattr(obj, k)
            objV = auxObjV.get() if isinstance(auxObjV, (LoggedValue)) else auxObjV
            if v != objV:
                result[k] = (objV, v)
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

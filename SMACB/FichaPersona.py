import logging
from collections import defaultdict
from pprint import pp
from typing import Optional, Set, Dict, Tuple, List

import bs4
from CAPcore.LoggedClass import LoggedClass
from CAPcore.LoggedDict import LoggedDict
from CAPcore.LoggedValue import LoggedValue, extractValue, setNewValue
from CAPcore.Misc import copyDictWithTranslation, getUTC, onlySetElement
from CAPcore.Web import mergeURL, DownloadedPage, downloadPage
from pandas import Timestamp
from requests import HTTPError

from Utils.ParseoData import procesaCosasUtilesPlantilla, findLocucionNombre
from Utils.Web import prepareDownloading, getObjID, sentinel
from .Constants import URL_BASE, URLIMG2IGNORE, POSABREV2NOMBRE
from .FichaClub import FichaClubPersona, FichaClubJugador, FichaClubEntrenador
from .PartidoACB import PartidoACB
from .Trayectoria import Trayectoria

CAMBIOSENTRENADORES = defaultdict(LoggedDict)
CAMBIOSJUGADORES = defaultdict(LoggedDict)

CLAVESFICHAPERSONA = ['URL', 'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', 'club', 'edicion']
CLAVESFICHAJUGADOR = ['posicion', 'altura', 'licencia', 'junior']  # ,'dorsal'
CLAVESFICHAENTRENADOR = {}  # 'dorsal'

VALIDPERSONATYPES = {'jugador', 'entrenador'}

PERSONABASICTAGS = {'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', 'persId'}


class FichaPersona(LoggedClass):
    CAMPOSPARALOG = []

    def __init__(self, **kwargs):
        if 'id' not in kwargs:
            raise ValueError(f"Ficha nueva sin 'persId': {kwargs}")
        self.persId: str = kwargs['id']

        tipoPers: Optional[str] = kwargs.get('tipoFicha', None)
        if tipoPers not in VALIDPERSONATYPES:
            raise ValueError(f"Persona Id '{self.persId}' Tipo '{tipoPers}' no válido. Aceptados: {VALIDPERSONATYPES}")
        self.tipoFicha: str = tipoPers

        super().__init__(**kwargs)

        if 'changeInfo' not in kwargs:
            changeInfo = {}
            kwargs['changeInfo'] = changeInfo

        self.sinDatos: Optional[bool] = None
        self.URL: Optional[str] = None
        self.trayectoria: Optional[Trayectoria] = None
        self.edicion: Optional[str] = None

        self.audioURL: Optional[str] = None
        self.nombre: LoggedValue = LoggedValue(None)
        self.alias: LoggedValue = LoggedValue(None)
        self.lugarNac: Optional[str] = None
        self.fechaNac: Optional[Timestamp] = None
        self.nacionalidad: LoggedValue = LoggedValue(None)
        self.nombresConocidos: Set[str] = set()
        self.fotos: Set[str] = set()
        self.urlConocidas: Set[str] = set()

        self.equipos: Set[str] = set()
        self.club: LoggedValue = LoggedValue(None)
        self.ultClub: Optional[str] = None

        self.fichasClub: Dict[str, FichaClubPersona] = {}
        self.partsClub: Dict[str, PartidosClub] = {}

        self.actualizaBioBasic(**kwargs)
        self.partsTemporada: PartidosClub = PartidosClub(persId=self.persId, tipoFicha=self.tipoFicha,
                                                         edicion=self.edicion, clubId=None)

    def actualizaBio(self, changeInfo=sentinel, **kwargs):
        """
        Para actualizar la biografía, si hay cosas específicas, añadirla a la clase derivada

        :param changeInfo:
        :param kwargs:
        :return:
        """

        if changeInfo is sentinel:
            changeInfo = {}
        result = False

        result |= updateFieldsWithLogged(data=self, keyList=self.varClaves(), changeInfo=changeInfo, **kwargs)

        if changeInfo:
            self.varCambios()[self.persId].update(changeInfo)

        return result

    def actualizaBioBasic(self, changeInfo=sentinel, **kwargs) -> bool:
        timestamp = kwargs.get('timestamp', getUTC())
        if changeInfo is sentinel:
            changeInfo = {}
        result = False

        result |= updateFieldsWithLogged(data=self, keyList=CLAVESFICHAPERSONA, changeInfo=changeInfo, **kwargs)

        if 'URL' in kwargs:
            self.urlConocidas.add(kwargs['URL'])

        if extractValue(self.nombre) is not None and extractValue(self.nombre) not in self.nombresConocidos:
            result |= True
            self.nombresConocidos.add(extractValue(self.nombre))

        if extractValue(self.alias) is not None and extractValue(self.alias) not in self.nombresConocidos:
            result |= True
            self.nombresConocidos.add(extractValue(self.alias))

        result |= self.updateFoto(urlFoto=kwargs.get('urlFoto', None), urlBase=self.URL, changeDict=changeInfo)

        ultClub = kwargs.get('club', None)
        currentClub = self.ultClub
        if ultClub is not None and ultClub != self.ultClub:
            if self.ultClub in self.partsClub:
                self.fichasClub[ultClub].bajaClub(timestamp=timestamp)
            self.equipos.add(ultClub)
            self.ultClub = ultClub
            self.fichasClub[self.ultClub] = self.nuevaFichaClub(persId=self.persId, clubId=ultClub,
                                                                changeInfo=changeInfo, **kwargs)
            changeInfo['club'] = (currentClub, ultClub)
            result |= True

        return result

    def buildURL(self):
        if self.tipoFicha is None:
            raise ValueError("buildURL: type of data unset")
        if self.tipoFicha not in VALIDPERSONATYPES:
            raise ValueError(f"buildURL: unknown type of data. Valid ones: {', '.join(sorted(VALIDPERSONATYPES))}")

        newPathList = ['', self.tipoFicha, 'temporada-a-temporada', 'id', self.persId]
        newPath = '/'.join(newPathList)

        result = mergeURL(URL_BASE, newPath)

        return result

    def infoFichaStr(self) -> Tuple[str, str]:
        raise NotImplementedError("infoFichaStr tiene que estar en las clases derivadas")

    def nombreFicha(self, trads: Optional[Dict] = None):
        nombreStr = extractValue(self.alias) or extractValue(self.nombre)
        fechaNacStr = "No Fnac" if self.fechaNac is None else self.fechaNac.strftime('%Y-%m-%d')
        gamesStr = self.partsTemporada.partsClub2str(trads=trads) if self.ultClub is None else self.partsClub[
            self.ultClub].partsClub2str(trads=trads)
        prefPers, datosPers = self.infoFichaStr()
        eqPlural = "s" if len(self.equipos) != 1 else ""

        return (f"{prefPers}: {nombreStr} ({self.persId}) {fechaNacStr} {datosPers} "
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
            raise ValueError(f"FichaPersona.fromURL: incapaz de sacar ID de f'{url}'. Buscados 'ver' e 'persId'")
        newData = {'persId': persId}
        if datos is not None:
            newData.update(datos)

        result = cls(**newData)
        result.actualizaDatosWeb(browser, config, home)

        return result

    @classmethod
    def fromPartido(cls, idPersona: str, datosPartido: Optional[dict] = None, **kwargs):
        """
        Crear una ficha de jugador a partir de los datos del partido. Bien porque no se descarguen fichas,
        bien como fallback
        :param idPersona: Código del jugador/entrenador
        :param datosPartido: Info del partido (de PartidoACB.Jugadores
        :param kwargs: parámetros que no vienen en datosPartido (timestamp)
        :return: Nuevo objeto creado
        """
        TRFICHAPERS = {'IDequipo': 'club', 'codigo': 'id', 'nombres': 'alias'}
        EXFICHAPERS = {'competicion', 'jornada', 'equipo', 'CODequipo', 'rival', 'CODrival', 'IDrival',
                       'url', 'estado', 'esLocal', 'haGanado', 'estads', 'esJugador', 'entrenador', 'haJugado',
                       'esTitular', 'linkPersona', }

        if datosPartido is None:
            datosPartido = {}

        fichaPers = {'id': idPersona}
        if 'linkPersona' in datosPartido:
            fichaPers['URL'] = mergeURL(URL_BASE, datosPartido['linkPersona']).removesuffix(".html").replace(" ", "-")
        fichaPers.update(kwargs)

        auxDatosPartido = copyDictWithTranslation(source=datosPartido, translation=TRFICHAPERS, excludes=EXFICHAPERS)
        fichaPers.update(auxDatosPartido)

        return cls(**fichaPers)

    def ficha2dict(self, club: str = None, partsClub: bool = False) -> Dict[str, str]:
        result = {k: getattr(self, k) for k in PERSONABASICTAGS}
        return result

    def nuevaFichaClub(self, **kwargs):
        raise NotImplementedError("nuevaFichaClub tiene que estar en las clases derivadas")

    def nuevoPartido(self, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """
        result = False

        dicTipo = partido.Jugadores if self.tipoFicha == 'jugador' else partido.Entrenadores

        if self.persId not in dicTipo:
            raise ValueError(
                f"{self.tipoFicha.capitalize()}: '{self.nombre}' ({self.persId}) no ha jugado partido {partido.url}")

        datosPersPart = dicTipo[self.persId]
        eqPersona = datosPersPart['IDequipo']
        timestamp = partido.timestamp

        result |= self.partsTemporada.addPartido(persona=self, partido=partido)

        if eqPersona != self.ultClub:
            self.fichasClub[self.ultClub].bajaClub(persId=self.persId, clubId=self.ultClub, timestamp=timestamp)
            self.fichasClub[eqPersona] = self.nuevaFichaClub(persId=self.persId, clubId=self.ultClub,
                                                             **datosPersPart)
            self.ultClub = eqPersona
            print("CAP nuevo club SMACB/FichaPersona.py:270")
            pp(self.fichasClub[eqPersona])

        if eqPersona not in self.partsClub:
            self.partsClub[eqPersona] = PartidosClub(persId=self.persId, tipoFicha=self.tipoFicha, edicion=self.edicion,
                                                     clubId=eqPersona)
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

    def varCambios(self):
        return NotImplementedError("varCambios tiene que estar en las clases derivadas")

    def varClaves(self):
        return NotImplementedError("varClaves tiene que estar en las clases derivadas")


class FichaJugador(FichaPersona):
    def __init__(self, **kwargs):
        changesInfo = {'NuevaFicha': (None, True)}
        self.posicion = None
        self.altura = None
        self.licencia = None
        self.junior = None

        super().__init__(NuevaFicha=True, tipoFicha='jugador', changesInfo=changesInfo, **kwargs)

        self.actualizaBio(changeInfo=changesInfo, **kwargs)

        CAMBIOSJUGADORES[self.persId].update(changesInfo)

    def infoFichaStr(self) -> Tuple[str, str]:
        alturaStr = f"{self.altura}cm " if (self.altura is not None) and (self.altura > 0) else ""
        posStr = f"{self.posicion}" if (self.posicion is not None) and (self.posicion != "") else ""

        prefix = "Jug"
        cadenaStr = f"{alturaStr}{posStr}"

        return prefix, cadenaStr

    def nuevaFichaClub(self, **kwargs):
        return FichaClubJugador(**kwargs)

    def varCambios(self):
        return CAMBIOSJUGADORES

    def varClaves(self):
        return CLAVESFICHAJUGADOR

    # @staticmethod
    # def fromPartido(idJugador: str, datosPartido: Optional[dict] = None, **kwargs):
    #     """
    #     Crear una ficha de jugador a partir de los datos del partido. Bien porque no se descarguen fichas,
    #     bien como fallback
    #     :param idJugador: Código del jugador
    #     :param datosPartido: Info del partido (de PartidoACB.Jugadores
    #     :param kwargs: parámetros que no vienen en datosPartido (timestamp)
    #     :return: Nuevo objeto creado
    #     """
    #     TRFICHAJUG = {'IDequipo': 'club', 'codigo': 'id', 'nombres': 'alias'}
    #     EXFICHAJUG = {'competicion', 'temporada', 'jornada', 'equipo', 'CODequipo', 'rival', 'CODrival', 'IDrival',
    #                 'url', 'estado', 'esLocal', 'haGanado', 'estads', 'esJugador', 'entrenador', 'haJugado', 'dorsal',
    #                   'esTitular', 'linkPersona', }
    #
    #     if datosPartido is None:
    #         datosPartido = {}
    #
    #     fichaJug = {'id': idJugador}
    #     if 'linkPersona' in datosPartido:
    #         fichaJug['URL'] = mergeURL(URL_BASE, datosPartido['linkPersona'])
    #     fichaJug.update(kwargs)
    #
    #     auxDatosPartido = copyDictWithTranslation(source=datosPartido, translation=TRFICHAJUG, excludes=EXFICHAJUG)
    #     fichaJug.update(auxDatosPartido)
    #
    #     return FichaJugador(**fichaJug)

    # @staticmethod
    # def fromURL(urlFicha, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):
    #     browser, config = prepareDownloading(browser, config)
    #
    #     try:
    #         fichaJug = descargaYparseaURLficha(urlFicha, datosPartido=datosPartido, home=home, browser=browser,
    #                                            config=config)
    #     except HTTPError:
    #         logging.exception("Problemas descargando jugador '%s'", urlFicha)
    #         return None
    #
    #     return FichaJugador(**fichaJug)

    # @staticmethod
    # def fromDatosPlantilla(datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None, home=None,
    #                        browser=None, config=None
    #                        ):
    #     if datosFichaPlantilla is None:
    #         return None
    #     datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)
    #
    #     newData = {}
    #     newData.update(datosFichaPlantilla)
    #
    #     try:
    #         fichaJug = descargaYparseaURLficha(datosFichaPlantilla['URL'], home=home, browser=browser, config=config)
    #         newData.update(fichaJug)
    #     except HTTPError:
    #         logging.exception("Problemas descargando jugador '%s'", datosFichaPlantilla['URL'])
    #
    #     return FichaJugador(**newData)
    #
    # def actualizaFromWeb(self, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):
    #
    #     result = False
    #     changeInfo = {}
    #
    #     result |= self.addAtributosQueFaltan()
    #
    #     browser, config = prepareDownloading(browser, config)
    #     newData = descargaYparseaURLficha(self.URL, datosPartido=datosPartido, home=home, browser=browser,
    #                                       config=config)
    #
    #     if self.sinDatos is None or self.sinDatos:
    #         self.sinDatos = newData.get('sinDatos', False)
    #         result = True
    #
    #     result |= self.updateFichaJugadorFromDownloadedData(changeInfo, newData)
    #
    #     if result:
    #         self.timestamp = newData.get('timestamp', getUTC())
    #         if changeInfo:
    #             CAMBIOSJUGADORES[self.id].update(changeInfo)
    #
    #     return result
    #
    # def actualizaFromPlantilla(self, datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None):
    #     if datosFichaPlantilla is None:
    #         return False
    #     datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)
    #
    #     result = False
    #     changeInfo = {}
    #
    #     result |= self.addAtributosQueFaltan()
    #
    #     result |= self.updateFichaJugadorFromDownloadedData(changeInfo, datosFichaPlantilla)
    #
    #     if result:
    #         self.timestamp = datosFichaPlantilla.get('timestamp', getUTC())
    #         if changeInfo:
    #             CAMBIOSJUGADORES[self.id].update(changeInfo)
    #
    #     return result
    #
    # def updateFichaJugadorFromDownloadedData(self, changeInfo, newData):
    #     result = False
    #     # No hay necesidad de poner la URL en el informe
    #     if 'URL' in newData and self.URL != newData['URL']:
    #         self.urlConocidas.add(newData['URL'])
    #         self.URL = newData['URL']
    #         result |= True
    #
    #     for k in CLAVESFICHAJUGADOR:
    #         if k not in newData:
    #             continue
    #         if getattr(self, k) != newData[k]:
    #             result |= True
    #             changeInfo[k] = (getattr(self, k), newData[k])
    #             setattr(self, k, newData[k])
    #
    #     if self.nombre is not None:
    #         self.nombresConocidos.add(self.nombre)
    #         result |= True
    #
    #     if self.alias is not None:
    #         self.nombresConocidos.add(self.alias)
    #         result |= True
    #
    #     if 'urlFoto' in newData:
    #         result |= self.updateFoto(newData['urlFoto'], self.URL, changeInfo)
    #
    #     ultClub = newData.get('club', None)
    #     if self.ultClub != ultClub:
    #         result |= True
    #         if ultClub is not None:
    #             result |= (ultClub not in self.equipos)
    #             self.equipos.add(ultClub)
    #             if self.ultClub != ultClub:
    #                 if (self.ultClub is None) or (newData.get('activo', False)):
    #                     changeInfo['ultClub'] = (self.ultClub, ultClub)
    #                     self.ultClub = ultClub
    #                     result |= True
    #     return result
    #
    #
    # def limpiaPartidos(self):
    #     self.primPartidoP = None
    #     self.ultPartidoP = None
    #     self.primPartidoT = None
    #     self.ultPartidoT = None
    #     self.partidos = set()
    #     self.timestamp = getUTC()
    #
    # def __add__(self, other):
    #     CLAVESAIGNORAR = ['id', 'url', 'timestamp', 'primPartidoP', 'ultPartidoP', 'primPartidoT', 'ultPartidoT',
    #                       'partidos']
    #     if self.id != other.id:
    #         raise ValueError(f"Claves de fichas no coinciden '{self.nombre}' {self.id} != {other.id}")
    #
    #     changes = False
    #     newer = self.timestamp < other.timestamp
    #     for k in vars(other).keys():
    #         if k in CLAVESAIGNORAR:
    #             continue
    #         if not hasattr(other, k) or getattr(other, k) is None:
    #             continue
    #         if (getattr(self, k) is None and getattr(other, k) is not None) or (
    #                 newer and getattr(self, k) != getattr(other, k)):
    #             setattr(self, k, getattr(other, k))
    #             changes = True
    #
    #     return changes
    #
    # def dictDatosJugador(self):
    #     result = {k: getattr(self, k) for k in CLAVESDICT}
    #     result['numEquipos'] = len(self.equipos)
    #     result['numPartidos'] = len(self.partidos)
    #     result['pos'] = TRADPOSICION.get(self.posicion, '**')
    #
    #     return result


class FichaEntrenador(FichaPersona):
    def __init__(self, **kwargs):
        changesInfo = {'NuevaFicha': (None, True)}

        super().__init__(NuevaFicha=True, tipoFicha='entrenador', changesInfo=changesInfo, **kwargs)

        self.actualizaBio(changeInfo=changesInfo, **kwargs)

        self.varCambios()[self.persId].update(changesInfo)

    def infoFichaStr(self, club: Optional[str] = None) -> Tuple[str, str]:
        prefix = "Ent"
        cadenaStr = "Sin datos puesto"

        auxClub = club
        if club is None:
            auxClub = self.ultClub
        if self.fichasClub[auxClub]:
            cadenaStr = self.fichasClub[auxClub].fichaCl2str()

        return prefix, cadenaStr

    def nuevaFichaClub(self, **kwargs):
        return FichaClubEntrenador(**kwargs)

    def varCambios(self):
        return CAMBIOSENTRENADORES

    def varClaves(self):
        return CLAVESFICHAENTRENADOR


class PartidosClub:
    def __init__(self, persId: str, tipoFicha: str, edicion: Optional[str], clubId: Optional[str]):
        self.persId: str = persId
        self.tipoFicha: str = tipoFicha
        self.edicion: Optional[str] = edicion
        self.clubID: Optional[str] = clubId
        self.equipos: Set[str] = set()

        self.primPartidoP: Optional[str] = None
        self.ultPartidoP: Optional[str] = None
        self.primPartidoT: Optional[Timestamp] = None
        self.ultPartidoT: Optional[Timestamp] = None
        self.partidos: Set[str] = set()

    def addPartido(self, persona: FichaPersona, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """

        dicTipo = partido.Jugadores if persona.tipoFicha == 'jugador' else partido.Entrenadores

        if self.persId not in dicTipo:
            raise ValueError(
                f"{persona.tipoFicha.capitalize()}: '{persona.nombre}' ({self.persId}) no ha jugado partido "
                f"{partido.url}")

        if partido.url in self.partidos:
            return False

        datosPersPart = dicTipo[self.persId]

        if datosPersPart['edicion'] != self.edicion:
            raise ValueError(
                f"Temporada del partido '{datosPersPart['edicion']}' no corresponde a la temporada aceptada '{self.edicion}'")

        eqJugador = datosPersPart['IDequipo']
        if self.clubID is None:
            self.equipos.add(eqJugador)
        else:
            if eqJugador != self.clubID:
                raise ValueError(
                    f"{persona.tipoFicha.capitalize()}: '{persona.nombre}' ({self.persId}) Añadiendo {partido.url} a "
                    f"registro incorrecto. Registro: '{self.clubID}'. Partido: '{eqJugador}'")

        self.partidos.add(partido.url)

        if persona.ultClub is None:
            persona.ultClub = datosPersPart['IDequipo']
        persona.equipos.add(datosPersPart['IDequipo'])

        if (self.primPartidoT is None) or (partido.fechaPartido < self.primPartidoT):
            self.primPartidoP = partido.url
            self.primPartidoT = partido.fechaPartido

        if (self.ultPartidoT is None) or (partido.fechaPartido > self.ultPartidoT):
            self.ultPartidoP = partido.url
            self.ultPartidoT = partido.fechaPartido
        return True

    def partsClub2str(self, trads: Optional[Dict] = None) -> str:
        FORMATOFECHA = '%Y-%m-%d'
        pluralClstr = "s" if len(self.equipos) > 1 else ""

        eqStr = f"Temp:{self.edicion} ({len(self.equipos)} eq{pluralClstr})"
        if self.clubID is not None:
            eqStr = f"IdClub:{self.clubID}@{self.edicion}"
            if trads is not None:
                tradCl = trads.get('i2c', {}).get(self.clubID, None)
                if tradCl:
                    tradName = onlySetElement(tradCl)
                    eqStr = f"{tradName}@{self.edicion}"

        partsStr = "Sin partidos registrados"
        if len(self.partidos):
            pluralPartsStr = "s" if len(self.partidos) > 1 else ""
            partsStr = f"{len(self.partidos)} part{pluralPartsStr}: {self.primPartidoT.strftime(FORMATOFECHA)} -> {self.ultPartidoT.strftime(FORMATOFECHA)}"

        result = f"{eqStr} {partsStr}"

        return result

    __str__ = partsClub2str
    __repr__ = partsClub2str


def extraeDatosPersonales(datosPag: Optional[DownloadedPage], datosPartido: Optional[dict] = None):
    """
    Saca la información de las personas de la ficha personal en ACB.com
    :param datosPag:
    :param datosPartido:
    :return:
    """
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


def updateFieldsWithLogged(data, keyList: List[str], changeInfo: object = sentinel, **kwargs) -> bool:
    if changeInfo is sentinel:
        changeInfo = {}

    result = False
    for k in keyList:
        if k not in kwargs:
            continue
        oldV = getattr(data, k)
        v = extractValue(oldV)
        if v != kwargs[k]:
            result |= True
            newVal = setNewValue(oldV, kwargs[k])
            setattr(data, k, newVal)
            changeInfo[k] = (v, kwargs[k])
    return result


def descargaYparseaURLficha(urlFicha, datosPartido: Optional[dict] = None, home=None, browser=None, config=None
                            ) -> dict:
    browser, config = prepareDownloading(browser, config)

    auxResult = {}
    # Asume que todo va a fallar
    if datosPartido is not None:
        auxResult['sinDatos'] = True
        auxResult['id'] = datosPartido['codigo']
        auxResult['alias'] = datosPartido['nombre']

    logging.info("Descargando ficha jugador '%s'", urlFicha)
    try:
        fichaJug: DownloadedPage = downloadPage(urlFicha, home=home, browser=browser, config=config)

        auxResult['URL'] = browser.get_url()
        auxResult['timestamp'] = fichaJug.timestamp

        auxResult['id'] = getObjID(urlFicha, 'ver')

        fichaData: bs4.BeautifulSoup = fichaJug.data

        cosasUtiles: Optional[bs4.BeautifulSoup] = fichaData.find(name='div', attrs={'class': 'datos'})

        if cosasUtiles is not None:
            auxResult.update(procesaCosasUtilesPlantilla(data=cosasUtiles, urlRef=auxResult['URL']))

        auxResult.update(findLocucionNombre(data=fichaData))

    except HTTPError:
        logging.exception("descargaYparseaURLficha: problemas descargando '%s'", urlFicha)

    result = {k: v for k, v in auxResult.items() if (v is not None) and (v != "")}
    return result


def muestraDiferenciasJugador(jugador, changeInfo):
    auxChangeStr = ", ".join([f"{k}: '{changeInfo[k][0]}'->'{changeInfo[k][1]}'" for k in sorted(changeInfo.keys())])
    changeStr = f" Cambios: {auxChangeStr} " if auxChangeStr else ""
    print(f"Ficha actualizada: {jugador}. {changeStr}")


def adaptaDatosFichaPlantilla(datosFichaPlantilla: dict, idClub: Optional[str]) -> dict:
    if 'pos' in datosFichaPlantilla:
        auxPos = POSABREV2NOMBRE.get(datosFichaPlantilla.pop('pos'), "?")
        if auxPos != "?":
            datosFichaPlantilla['posicion'] = auxPos
    if idClub is not None:
        datosFichaPlantilla['club'] = idClub

    return datosFichaPlantilla

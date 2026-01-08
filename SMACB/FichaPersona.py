import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional, Set, Dict, Tuple, List, Any

import bs4
from CAPcore.DataChangeLogger import DataChangesTuples
from CAPcore.LoggedClass import diffDicts, LoggedClassGenerator
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

DataLogger = LoggedClassGenerator(DataChangesTuples)

CAMBIOSENTRENADORES = defaultdict(lambda: {'cambios': set()})
CAMBIOSJUGADORES = defaultdict(lambda: {'cambios': set()})

CLAVESFICHAPERSONA = ['URL', 'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', 'club', 'edicion']
CLAVESFICHAJUGADOR = ['posicion', 'altura', 'licencia', 'junior']  # ,'dorsal'

VALIDPERSONATYPES = {'jugador', 'entrenador'}

PERSONABASICTAGS = {'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', 'persId'}


class FichaPersona(DataLogger):
    CLAVESPERSONA = ['URL', 'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad', 'club', ]
    EXCLUDESPERSONA = ['persId', 'tipoFicha', 'sinDatos', 'trayectoria', 'nombresConocidos', 'equipos',
                       'ultClub', 'fichasClub', 'partsClub', 'timestamp', 'changeLog', 'partsTemporada', 'urlConocidas',
                       'fotos']

    def __init__(self, persId: str, tipoFicha: str, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        self.persId: str = persId

        if tipoFicha not in VALIDPERSONATYPES:
            raise ValueError(f"Persona Id '{self.persId}' Tipo '{tipoFicha}' no válido. Aceptados: {VALIDPERSONATYPES}")
        self.tipoFicha: str = tipoFicha
        self.edicion: Optional[str] = None

        self.URL: Optional[str] = None
        self.nombre: LoggedValue = LoggedValue(None)
        self.alias: LoggedValue = LoggedValue(None)
        self.lugarNac: Optional[str] = None
        self.fechaNac: Optional[Timestamp] = None
        self.nacionalidad: LoggedValue = LoggedValue(None)
        self.audioURL: Optional[str] = None
        self.club: LoggedValue = LoggedValue(None)

        self.sinDatos: Optional[bool] = None  # Ha fallado la descarga de la ficha en ACB.com
        self.nombresConocidos: Set[str] = set()
        self.fotos: Set[str] = set()
        self.urlConocidas: Set[str] = set()
        self.trayectoria: Optional[Trayectoria] = None

        self.equipos: Set[str] = set()
        self.ultClub: Optional[str] = None
        self.fichasClub: Dict[str, FichaClubPersona] = {}
        self.partsClub: Dict[str, PartidosClub] = {}
        self.partsTemporada: Optional[PartidosClub] = None
        super().__init__(**kwargs)

        self.actualizaBioBasic(**kwargs)

        currentValues = self.ficha2dict()
        self.partsTemporada = PartidosClub(persId=self.persId, tipoFicha=self.tipoFicha,
                                           edicion=self.edicion, clubId=None)

        newValues = self.ficha2dict()

        changeInfo = diffDicts(currentValues, newValues)
        changeInfo['Nuevaficha'] = (None, True)
        self.updateDataLog(changeInfo=changeInfo, timestamp=timestamp)
        self.varCambios()[self.persId]['nuevo'] = True
        self.varCambios()[self.persId]['cambios'].add(timestamp)

    def actualizaBio(self, **kwargs):
        """
        Para actualizar la biografía, si hay cosas específicas, añadirla a la clase derivada

        :param changeInfo:
        :param kwargs:
        :return:
        """
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        changes = False
        currentValues = self.ficha2dict()
        changes |= self.updateDataFields(excludes=self.EXCLUDESPERSONA, **kwargs)
        newValues = self.ficha2dict()

        self.updateDataLog(changeInfo=diffDicts(currentValues, newValues), timestamp=timestamp)
        if timestamp in self.changeLog:
            self.varCambios()[self.persId]['cambios'].add(timestamp)

        return changes

    def actualizaBioBasic(self, **kwargs) -> bool:
        timestamp = kwargs.get('timestamp', getUTC())

        currentValues = self.ficha2dict()

        changes = False
        changes |= self.updateDataFields(excludes=self.EXCLUDESPERSONA, **kwargs)

        if 'URL' in kwargs:
            self.urlConocidas.add(kwargs['URL'])

        currNombre = extractValue(self.nombre)
        if currNombre is not None and currNombre not in self.nombresConocidos:
            self.nombresConocidos.add(currNombre)
            changes |= True

        currAlias = extractValue(self.alias)
        if currAlias is not None and currAlias not in self.nombresConocidos:
            self.nombresConocidos.add(currAlias)
            changes |= True

        changes |= self.updateFoto(urlFoto=kwargs.get('urlFoto', None), urlBase=self.URL)

        ultClub = extractValue(self.club)
        if ultClub is not None and ultClub != self.ultClub:
            if self.ultClub in self.partsClub:
                self.fichasClub[ultClub].bajaClub(persId=self.persId, clubId=self.ultClub, timestamp=timestamp)
            self.equipos.add(ultClub)
            self.ultClub = ultClub
            self.fichasClub[self.ultClub] = self.nuevaFichaClub(persId=self.persId, clubId=ultClub,
                                                                **kwargs)
            if self.ultClub not in self.partsClub:
                self.partsClub[self.ultClub] = PartidosClub(persId=self.persId, tipoFicha=self.tipoFicha,
                                                            edicion=self.edicion, clubId=self.ultClub)

            changes |= True

        newValues = self.ficha2dict()

        self.updateDataLog(changeInfo=diffDicts(currentValues, newValues), timestamp=timestamp)
        if timestamp in self.changeLog:
            self.varCambios()[self.persId]['cambios'].add(timestamp)

        return changes

    def buildURL(self):
        if self.tipoFicha is None:
            raise ValueError("buildURL: type of data unset")
        if self.tipoFicha not in VALIDPERSONATYPES:
            raise ValueError(f"buildURL: unknown type of data. Valid ones: {', '.join(sorted(VALIDPERSONATYPES))}")

        newPathList = ['', self.tipoFicha, 'temporada-a-temporada', 'id', self.persId]
        newPath = '/'.join(newPathList)

        result = mergeURL(URL_BASE, newPath)

        return result

    def infoFichaStr(self, club: Optional[str] = None, trads: Optional[Dict] = None) -> Tuple[str, str]:
        raise NotImplementedError("infoFichaStr tiene que estar en las clases derivadas")

    def nombreFicha(self, trads: Optional[Dict] = None):
        nombreStr = extractValue(self.alias) or extractValue(self.nombre)
        fechaNacStr = "No Fnac" if self.fechaNac is None else self.fechaNac.strftime('%Y-%m-%d')
        gamesStr = self.partsTemporada.partsClub2str(trads=trads) if self.ultClub is None else self.partsClub[
            self.ultClub].partsClub2str(trads=trads)
        prefPers, datosPers = self.infoFichaStr(trads=trads)
        eqPlural = "s" if len(self.equipos) != 1 else ""

        return (f"{prefPers}: {nombreStr} ({self.persId}) {fechaNacStr} {datosPers} "
                f"({len(self.equipos)} eq{eqPlural}) {gamesStr}")

    def nuevoPartido(self, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """
        changes = False

        currentValues = self.ficha2dict()

        dicTipo = partido.Jugadores if self.tipoFicha == 'jugador' else partido.Entrenadores

        if self.persId not in dicTipo:
            raise ValueError(
                f"{self.tipoFicha.capitalize()}: '{self.nombre}' ({self.persId}) no ha jugado partido {partido.url}")

        datosPersPart = dicTipo[self.persId]
        eqPersona = datosPersPart['IDequipo']
        timestamp = partido.fechaPartido.to_pydatetime()

        changes |= self.partsTemporada.addPartido(persona=self, partido=partido)

        if eqPersona != self.ultClub:
            self.fichasClub[self.ultClub].bajaClub(persId=self.persId, clubId=self.ultClub, timestamp=timestamp)
            self.fichasClub[eqPersona] = self.nuevaFichaClub(persId=self.persId, clubId=self.ultClub,
                                                             **datosPersPart)
            self.updateDataFields(timestamp=timestamp, club=eqPersona)
            self.ultClub = eqPersona

        if eqPersona not in self.partsClub:
            self.partsClub[eqPersona] = PartidosClub(persId=self.persId, tipoFicha=self.tipoFicha, edicion=self.edicion,
                                                     clubId=eqPersona)
            changes = True

        changes |= self.partsClub[eqPersona].addPartido(persona=self, partido=partido)

        newValues = self.ficha2dict()

        self.updateDataLog(changeInfo=diffDicts(currentValues, newValues), timestamp=timestamp)
        if timestamp in self.changeLog:
            self.varCambios()[self.persId]['cambios'].add(timestamp)

        return changes

    def varCambios(self):
        raise NotImplementedError("varCambios tiene que estar en las clases derivadas")

    def clavesSubclase(self):
        raise NotImplementedError("varClaves tiene que estar en las clases derivadas")

    def bajaClub(self, clubId: str, timestamp: Optional[datetime] = None) -> bool:
        changes = False
        if timestamp is None:
            timestamp = getUTC()
        if clubId not in self.equipos:
            raise KeyError(f"{self} no ha jugado en club {clubId}")
        if clubId not in self.fichasClub:
            raise KeyError(f"{self} no tiene ficha en club {clubId}")

        changes |= self.fichasClub[clubId].bajaClub(persId=self.persId, clubId=clubId, timestamp=timestamp)

        if extractValue(self.club) == clubId:
            changes |= self.updateDataFields(timestamp=timestamp, club=None)

        if extractValue(self.ultClub) == clubId:
            changes |= self.updateDataFields(timestamp=timestamp, ultClub=None)

        return changes

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
        TRFICHAPERS = {'IDequipo': 'club', 'codigo': 'persId', 'nombres': 'alias'}
        EXFICHAPERS = {'competicion', 'jornada', 'equipo', 'CODequipo', 'rival', 'CODrival', 'IDrival',
                       'url', 'estado', 'esLocal', 'haGanado', 'estads', 'esJugador', 'entrenador', 'haJugado',
                       'esTitular', 'linkPersona', }

        if datosPartido is None:
            datosPartido = {}
        fichaPers = {'id': idPersona}
        fichaPers.update(kwargs)
        if 'linkPersona' in datosPartido:
            fichaPers['URL'] = mergeURL(URL_BASE, datosPartido['linkPersona']).removesuffix(".html").replace(" ", "-")

        auxDatosPartido = copyDictWithTranslation(source=datosPartido, translation=TRFICHAPERS, excludes=EXFICHAPERS)
        fichaPers.update(auxDatosPartido)

        return cls(**fichaPers)

    def ficha2dict(self) -> Dict[str, Any]:
        result = self.class2dict(keyList=self.CLAVESPERSONA + self.clavesSubclase(), mapFunc=extractValue)
        if self.ultClub is not None and self.ultClub in self.fichasClub:
            datosFicha = self.fichasClub[self.ultClub].fichaCl2dict()
            result.update(datosFicha)

        return result

    def nuevaFichaClub(self, **kwargs):
        raise NotImplementedError("nuevaFichaClub tiene que estar en las clases derivadas")

    def actualizaDatosWeb(self, browser=None, config=None, home=None) -> bool:
        result = False
        pag = self.descargaPagina(home, browser, config)
        if pag is None:
            return False
        datosPersona = extraeDatosPersonales(datosPag=pag)
        result |= self.actualizaBio(**datosPersona)
        if self.trayectoria is None:
            self.trayectoria = Trayectoria.fromWebPage(data=pag)
            result |= True

        return result


class FichaJugador(FichaPersona):
    CLAVESFICHAJUGADOR = ['posicion', 'altura', 'licencia', 'junior', 'nacionalidad']

    def __init__(self, **kwargs):
        self.posicion = None
        self.altura = None
        self.licencia = None
        self.junior = None

        super().__init__(tipoFicha='jugador', **kwargs)

        self.actualizaBio(**kwargs)

        # CAMBIOSJUGADORES[self.persId].update()

    def infoFichaStr(self, club: Optional[str] = None, trads: Optional[Dict] = None) -> Tuple[str, str]:
        prefix = "Jug"

        valores2show = {k: v for k, v in {k: extractValue(getattr(self, k)) for k in self.CLAVESFICHAJUGADOR}.items() if
                        v is not None}

        auxClub = club
        clubStr = "Sin club"
        if club is None:  # Nos interesa el último
            auxClub = self.ultClub
        if auxClub is not None:  # En paro
            clubStr = clubId2str(auxClub, self.edicion, trads)
            if self.fichasClub[auxClub]:
                fichaClub: FichaClubJugador = self.fichasClub[auxClub]

                valoresFicha2show = {k: v for k, v in
                                     {k: extractValue(getattr(fichaClub, k)) for k in fichaClub.SUBCLASSCLAVES}.items()
                                     if
                                     v is not None}
                valores2show.update(valoresFicha2show)

        formatterJug = {'posicion': {}, 'altura': {'formato': "{}cm", 'extraCond': lambda x: x > 0},
                        'junior': {'formato': '(Junior) ', 'extraCond': lambda x: x},
                        'licencia': {}, 'dorsal': {'formato': "Dorsal: {}"}, 'nacionalidad': {'formato': "Nac: {}"}}

        strs2Show = formateaInfoJugador(valores2show, formatterJug)

        CLAVES2SHOW = ['posicion', 'altura', 'nacionalidad', 'licencia', 'junior', 'dorsal', ]

        cadenaStr = " ".join(strs2Show.get(k, "") for k in CLAVES2SHOW if k in strs2Show)
        if cadenaStr == "":
            return prefix, "Sin datos jugador"

        return prefix, clubStr + " " + cadenaStr

    def nuevaFichaClub(self, **kwargs):
        return FichaClubJugador(**kwargs)

    def varCambios(self):
        return CAMBIOSJUGADORES

    def clavesSubclase(self):
        return self.CLAVESFICHAJUGADOR

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
    CLAVESFICHAENTRENADOR = []

    def __init__(self, **kwargs):
        super().__init__(tipoFicha='entrenador', **kwargs)

        self.actualizaBio(**kwargs)

        # self.varCambios()[self.persId].update(changesInfo)

    def infoFichaStr(self, club: Optional[str] = None, trads: Optional[Dict] = None) -> Tuple[str, str]:
        prefix = "Ent"

        auxClub = club
        if club is None:  # Nos interesa el último
            auxClub = self.ultClub
        if auxClub is None:  # En paro
            cadenaStr = "Sin club"
        else:
            eqStr = f"IdClub:{auxClub}@{self.edicion}"
            if trads is not None:
                tradCl = trads.get('i2c', {}).get(auxClub, None)
                if tradCl:
                    tradName = onlySetElement(tradCl)
                    eqStr = f"'{tradName}'"

            cadenaStr = self.fichasClub[auxClub].fichaCl2str() if self.fichasClub[
                auxClub] else f"No hay datos para club {eqStr}"

        return prefix, cadenaStr

    def nuevaFichaClub(self, **kwargs):
        return FichaClubEntrenador(**kwargs)

    def varCambios(self):
        return CAMBIOSENTRENADORES

    def clavesSubclase(self):
        return self.CLAVESFICHAENTRENADOR


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
                f"Temporada del partido '{datosPersPart['edicion']}' no corresponde a la temporada "
                f"aceptada '{self.edicion}'")

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
        if self.partidos:
            pluralPartsStr = "s" if len(self.partidos) > 1 else ""
            partsStr = (f"{len(self.partidos)} part{pluralPartsStr}: {self.primPartidoT.strftime(FORMATOFECHA)} "
                        f"-> {self.ultPartidoT.strftime(FORMATOFECHA)}")

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


def clubId2str(club: str, edicion: str, trads: dict | None = None) -> str:
    eqStr = f"IdClub:{club}@{edicion}"
    if trads is not None:
        tradCl = trads.get('i2c', {}).get(club, None)
        if tradCl:
            tradName = onlySetElement(tradCl)
            eqStr = f"'{tradName}'"
    return eqStr


def formateaInfoJugador(valores: Dict[str, Any], formatter=Dict[str, Dict]) -> Dict[str, str]:
    FORMATODEFECTO = "{}"
    result = {}
    for k, v in valores.items():
        dataFormatter: Dict = formatter.get(k, {'formato': FORMATODEFECTO})
        formato: str = dataFormatter.get('formato', FORMATODEFECTO)
        extraCond = dataFormatter.get('extraCond', lambda x: x != "")
        if not extraCond(v):
            continue
        valResult = formato.format(v)
        result[k] = valResult

    return result

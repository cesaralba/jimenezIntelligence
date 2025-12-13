import logging
from collections import defaultdict
from time import gmtime
from typing import Optional

import bs4
from CAPcore.Misc import copyDictWithTranslation
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage
from requests import HTTPError

from SMACB.Constants import URLIMG2IGNORE, CLAVESFICHAJUGADOR, CLAVESDICT, TRADPOSICION, POSABREV2NOMBRE, URL_BASE
from SMACB.PartidoACB import PartidoACB
from Utils.ParseoData import findLocucionNombre, procesaCosasUtilesPlantilla
from Utils.Web import getObjID, prepareDownloading

CAMBIOSJUGADORES = defaultdict(dict)


class FichaJugador:
    def __init__(self, **kwargs):
        changesInfo = {'NuevoJugador': True}
        if 'id' not in kwargs:
            raise ValueError(f"Jugador nuevo sin 'id': {kwargs}")
        self.id = kwargs.get('id', None)
        self.URL = kwargs.get('URL', None)
        self.sinDatos: Optional[bool] = None

        self.timestamp = kwargs.get('timestamp', None)
        self.nombre = kwargs.get('nombre', None)
        self.alias = kwargs.get('alias', self.nombre)
        self.lugarNac = kwargs.get('lugarNac', None)
        self.fechaNac = kwargs.get('fechaNac', None)
        self.posicion = kwargs.get('posicion', None)
        self.altura = kwargs.get('altura', None)
        self.nacionalidad = kwargs.get('nacionalidad', None)
        self.licencia = kwargs.get('licencia', None)
        self.junior = kwargs.get('junior', False)
        self.audioURL = kwargs.get('audioURL', None)

        self.ultClub = None

        self.nombresConocidos = set()
        self.urlConocidas = set()
        self.fotos = set()

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

        addedData = {k: kwargs.get(k, None) for k in CLAVESFICHAJUGADOR if kwargs.get(k, None) is not None}
        changesInfo.update(addedData)
        CAMBIOSJUGADORES[self.id].update(changesInfo)

    def updateFoto(self, urlFoto: Optional[str], urlBase: Optional[str], changeDict: Optional[dict] = None):
        changes = False

        if urlFoto is not None and urlFoto not in URLIMG2IGNORE:
            changes = True
            newURL = mergeURL(urlBase, urlFoto)
            self.fotos.add(newURL)
            if changeDict:
                changeDict['urlFoto'] = ("", "Nueva")
        return changes

    @staticmethod
    def fromPartido(idJugador: str, datosPartido: Optional[dict] = None, **kwargs):
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

        return FichaJugador(**fichaJug)

    @staticmethod
    def fromURL(urlFicha, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):
        browser, config = prepareDownloading(browser, config)

        try:
            fichaJug = descargaYparseaURLficha(urlFicha, datosPartido=datosPartido, home=home, browser=browser,
                                               config=config)
        except HTTPError:
            logging.exception("Problemas descargando jugador '%s'", urlFicha)
            return None

        return FichaJugador(**fichaJug)

    @staticmethod
    def fromDatosPlantilla(datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None, home=None,
                           browser=None, config=None
                           ):
        if datosFichaPlantilla is None:
            return None
        datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)

        newData = {}
        newData.update(datosFichaPlantilla)

        try:
            fichaJug = descargaYparseaURLficha(datosFichaPlantilla['URL'], home=home, browser=browser, config=config)
            newData.update(fichaJug)
        except HTTPError:
            logging.exception("Problemas descargando jugador '%s'", datosFichaPlantilla['URL'])

        return FichaJugador(**newData)

    def actualizaFromWeb(self, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):

        result = False
        changeInfo = {}

        result |= self.addAtributosQueFaltan()

        browser, config = prepareDownloading(browser, config)
        newData = descargaYparseaURLficha(self.URL, datosPartido=datosPartido, home=home, browser=browser,
                                          config=config)

        if self.sinDatos is None or self.sinDatos:
            self.sinDatos = newData.get('sinDatos', False)
            result = True

        result |= self.updateFichaJugadorFromDownloadedData(changeInfo, newData)

        if result:
            self.timestamp = newData.get('timestamp', gmtime())
            if changeInfo:
                CAMBIOSJUGADORES[self.id].update(changeInfo)

        return result

    def actualizaFromPlantilla(self, datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None):
        if datosFichaPlantilla is None:
            return False
        datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)

        result = False
        changeInfo = {}

        result |= self.addAtributosQueFaltan()

        result |= self.updateFichaJugadorFromDownloadedData(changeInfo, datosFichaPlantilla)

        if result:
            self.timestamp = datosFichaPlantilla.get('timestamp', gmtime())
            if changeInfo:
                CAMBIOSJUGADORES[self.id].update(changeInfo)

        return result

    def updateFichaJugadorFromDownloadedData(self, changeInfo, newData):
        result = False
        # No hay necesidad de poner la URL en el informe
        if 'URL' in newData and self.URL != newData['URL']:
            self.urlConocidas.add(newData['URL'])
            self.URL = newData['URL']
            result |= True

        for k in CLAVESFICHAJUGADOR:
            if k not in newData:
                continue
            if getattr(self, k) != newData[k]:
                result |= True
                changeInfo[k] = (getattr(self, k), newData[k])
                setattr(self, k, newData[k])

        if self.nombre is not None:
            self.nombresConocidos.add(self.nombre)
            result |= True

        if self.alias is not None:
            self.nombresConocidos.add(self.alias)
            result |= True

        if 'urlFoto' in newData:
            result |= self.updateFoto(newData['urlFoto'], self.URL, changeInfo)

        ultClub = newData.get('club', None)
        if self.ultClub != ultClub:
            result |= True
            if ultClub is not None:
                result |= (ultClub not in self.equipos)
                self.equipos.add(ultClub)
                if self.ultClub != ultClub:
                    if (self.ultClub is None) or (newData.get('activo', False)):
                        changeInfo['ultClub'] = (self.ultClub, ultClub)
                        self.ultClub = ultClub
                        result |= True
        return result

    def addAtributosQueFaltan(self) -> bool:
        """
        Añade
        :param:
        :return: si ha habido cambios
        """
        changes = False
        if not hasattr(self, 'sinDatos'):
            changes = True
            setattr(self, 'sinDatos', None)
        if not hasattr(self, 'nombresConocidos'):
            changes = True
            setattr(self, 'nombresConocidos', set())
            if self.nombre is not None:
                self.nombresConocidos.add(self.nombre)
            if self.alias is not None:
                self.nombresConocidos.add(self.alias)
        if not hasattr(self, 'ultClub'):
            changes = True
            setattr(self, 'ultClub', None)
        if not hasattr(self, 'junior'):
            changes = True
            setattr(self, 'junior', None)
        if not hasattr(self, 'audioURL'):
            changes = True
            setattr(self, 'audioURL', None)
        if not hasattr(self, 'urlConocidas'):
            changes = True
            setattr(self, 'urlConocidas', set())
            self.urlConocidas.add(self.URL)
        return changes

    def nuevoPartido(self, partido: PartidoACB) -> bool:
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partidoACB
        :return: Si ha cambiado el objeto o no
        """

        if self.id not in partido.Jugadores:
            raise ValueError(f"Jugador '{self.nombre}' ({self.id}) no ha jugado partido {partido.url}")

        if partido.url in self.partidos:
            return False

        self.partidos.add(partido.url)
        logging.debug("Jugador [%s] %s ha jugado '%s'", self.id, self.nombre, partido.url)
        datosJug = partido.Jugadores[self.id]
        self.equipos.add(datosJug['IDequipo'])

        if self.ultClub is None:
            self.ultClub = datosJug['IDequipo']

        if (self.primPartidoT is None) or (partido.fechaPartido < self.primPartidoT):
            self.primPartidoP = partido.url
            self.primPartidoT = partido.fechaPartido

        if (self.ultPartidoT is None) or (partido.fechaPartido > self.ultPartidoT):
            self.ultPartidoP = partido.url
            self.ultPartidoT = partido.fechaPartido
        return True

    def __repr__(self):
        nombreStr = self.alias or self.nombre
        fechaNacStr = "Sin datos" if self.fechaNac is None else self.fechaNac.strftime('%Y-%m-%d')
        gamesStr = "Sin partidos registrados" if self.primPartidoT is None else (
            f"Parts:[{len(self.partidos)}] {self.primPartidoT.strftime('%Y-%m-%d')} -> "
            f"{self.ultPartidoT.strftime('%Y-%m-%d')}")
        eqPlural = "s" if len(self.equipos) != 1 else ""

        return (f"{nombreStr} ({self.id}) {fechaNacStr} "
                f"({len(self.equipos)} eq{eqPlural}) {gamesStr}")

    def nombreFicha(self):
        nombreStr = self.alias or self.nombre
        fechaNacStr = "Sin datos" if self.fechaNac is None else self.fechaNac.strftime('%Y-%m-%d')
        gamesStr = "Sin partidos registrados" if self.primPartidoT is None else (
            f"Parts:[{len(self.partidos)}] {self.primPartidoT.strftime('%Y-%m-%d')} -> "
            f"{self.ultPartidoT.strftime('%Y-%m-%d')}")
        alturaStr = f"{self.altura}cm " if (self.altura is not None) and (self.altura > 0) else ""
        posStr = f"{self.posicion}" if (self.posicion is not None) and (self.posicion != "") else ""
        eqPlural = "s" if len(self.equipos) != 1 else ""

        return (f"{nombreStr} ({self.id}) {fechaNacStr} {alturaStr}{posStr} "
                f"({len(self.equipos)} eq{eqPlural}) {gamesStr}")

    def limpiaPartidos(self):
        self.primPartidoP = None
        self.ultPartidoP = None
        self.primPartidoT = None
        self.ultPartidoT = None
        self.partidos = set()
        self.timestamp = gmtime()

    def __add__(self, other):
        CLAVESAIGNORAR = ['id', 'url', 'timestamp', 'primPartidoP', 'ultPartidoP', 'primPartidoT', 'ultPartidoT',
                          'partidos']
        if self.id != other.id:
            raise ValueError(f"Claves de fichas no coinciden '{self.nombre}' {self.id} != {other.id}")

        changes = False
        newer = self.timestamp < other.timestamp
        for k in vars(other).keys():
            if k in CLAVESAIGNORAR:
                continue
            if not hasattr(other, k) or getattr(other, k) is None:
                continue
            if (getattr(self, k) is None and getattr(other, k) is not None) or (
                    newer and getattr(self, k) != getattr(other, k)):
                setattr(self, k, getattr(other, k))
                changes = True

        return changes

    def dictDatosJugador(self):
        result = {k: getattr(self, k) for k in CLAVESDICT}
        result['numEquipos'] = len(self.equipos)
        result['numPartidos'] = len(self.partidos)
        result['pos'] = TRADPOSICION.get(self.posicion, '**')

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

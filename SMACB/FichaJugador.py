import re
from collections import defaultdict
from time import gmtime
from typing import Optional

import pandas as pd
from CAPcore.Misc import onlySetElement
from CAPcore.Web import downloadPage, mergeURL

from SMACB.Constants import URLIMG2IGNORE, CLAVESFICHAJUGADOR, CLAVESDICT, TRADPOSICION, POSABREV2NOMBRE
from Utils.FechaHora import PATRONFECHA
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
    def fromURL(urlFicha, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):
        browser, config = prepareDownloading(browser, config)

        fichaJug = descargaURLficha(urlFicha, datosPartido=datosPartido, home=home, browser=browser, config=config)
        print(fichaJug)
        return FichaJugador(**fichaJug)

    @staticmethod
    def fromDatosPlantilla(datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None):
        if datosFichaPlantilla is None:
            return None
        datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)

        return FichaJugador(**datosFichaPlantilla)

    def actualizaFicha(self, datosPartido: Optional[dict] = None, home=None, browser=None, config=None):

        changes = False
        changeInfo = dict()

        changes |= self.addAtributosQueFaltan()

        browser, config = prepareDownloading(browser, config)
        newData = descargaURLficha(self.URL, datosPartido=datosPartido, home=home, browser=browser, config=config)

        if self.sinDatos is None or self.sinDatos:
            self.sinDatos = newData.get('sinDatos', False)
            changes = True

        changes |= self.updateFichaJugadorFromDownloadedData(changeInfo, newData)

        if changes:
            self.timestamp = newData.get('timestamp', gmtime())
            CAMBIOSJUGADORES[self.id].update(changeInfo)

        return changes

    def actualizaFromPlantilla(self, datosFichaPlantilla: Optional[dict] = None, idClub: Optional[str] = None):
        if datosFichaPlantilla is None:
            return False
        datosFichaPlantilla = adaptaDatosFichaPlantilla(datosFichaPlantilla, idClub)

        result = False
        changeInfo = dict()

        result |= self.addAtributosQueFaltan()

        result |= self.updateFichaJugadorFromDownloadedData(changeInfo, datosFichaPlantilla)

        if result:
            self.timestamp = datosFichaPlantilla.get('timestamp', gmtime())
            print(self.id, )
            CAMBIOSJUGADORES[self.id].update(changeInfo)

        return result

    def updateFichaJugadorFromDownloadedData(self, changeInfo, newData):
        result = False
        # No hay necesidad de poner la URL en el informe
        if self.URL != datosFichaPlantilla['URL']:
            self.urlConocidas.add(datosFichaPlantilla['URL'])
            self.URL = datosFichaPlantilla['URL']
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
                self.equipos.add(ultClub)
                if (self.ultClub != ultClub):
                    changeInfo['ultClub'] = (self.ultClub, ultClub)
            self.ultClub = ultClub

        if result:
            self.timestamp = datosFichaPlantilla.get('timestamp', gmtime())
            print(self.id, )
            CAMBIOSJUGADORES[self.id].update(changeInfo)

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
            self.__setattr__('sinDatos', None)
        if not hasattr(self, 'nombresConocidos'):
            changes = True
            self.__setattr__('nombresConocidos', set())
            if self.nombre is not None:
                self.nombresConocidos.add(self.nombre)
            if self.alias is not None:
                self.nombresConocidos.add(self.alias)
        if not hasattr(self, 'ultClub'):
            changes = True
            self.__setattr__('ultClub', None)
        if not hasattr(self, 'urlConocidas'):
            changes = True
            self.__setattr__('urlConocidas', set())
            self.urlConocidas.add(self.URL)
        return changes

    def nuevoPartido(self, partido):
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

        datosJug = partido.Jugadores[self.id]
        self.equipos.add(datosJug['IDequipo'])

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
            f"{self.primPartidoT.strftime('%Y-%m-%d')} -> "
            f"{self.ultPartidoT.strftime('%Y-%m-%d')}")
        return (f"{nombreStr} ({self.id}) {fechaNacStr} P:[{len(self.partidos)}] "
                f"{gamesStr} ({len(self.equipos)})")

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


def descargaURLficha(urlFicha, datosPartido: Optional[dict] = None, home=None, browser=None, config=None) -> dict:
    browser, config = prepareDownloading(browser, config)

    result = dict()
    try:
        # Asume que todo va a fallar
        if datosPartido is not None:
            result['sinDatos'] = True
            result['nombre'] = datosPartido['nombre']

        fichaJug = downloadPage(urlFicha, home=home, browser=browser, config=config)

        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()

        result['id'] = getObjID(urlFicha, 'ver')

        fichaData = fichaJug.data

        cosasUtiles = fichaData.find(name='div', attrs={'class': 'datos'})

        if cosasUtiles is not None:
            result['urlFoto'] = cosasUtiles.find('div', attrs={'class': 'foto'}).find('img')['src']
            result['alias'] = cosasUtiles.find('h1').get_text().strip()
            result['sinDatos'] = False
            for row in cosasUtiles.findAll('div', {'class': ['datos_basicos', 'datos_secundarios']}):

                valor = row.find("span", {'class': 'roboto_condensed_bold'}).get_text().strip()
                classDiv = row.attrs['class']

                if 'equipo' in classDiv:
                    continue
                if 'dorsal' in classDiv:
                    continue
                if 'posicion' in classDiv:
                    result['posicion'] = valor
                elif 'altura' in classDiv:
                    REaltura = r'^(\d)[,.](\d{2})\s*m$'
                    reProc = re.match(REaltura, valor)
                    if reProc:
                        result['altura'] = 100 * int(reProc.group(1)) + int(reProc.group(2))
                    else:
                        print(cosasUtiles, f"ALTURA '{valor}' no casa RE '{REaltura}'")
                elif 'lugar_nacimiento' in classDiv:
                    result['lugarNac'] = valor
                elif 'fecha_nacimiento' in classDiv:
                    REfechaNac = r'^(?P<fechanac>\d{2}/\d{2}/\d{4})\s*.*'
                    reProc = re.match(REfechaNac, valor)
                    if reProc:
                        result['fechaNac'] = pd.to_datetime(reProc['fechanac'], format=PATRONFECHA)
                    else:
                        print("FECHANAC no casa RE", valor, REfechaNac)
                elif 'nacionalidad' in classDiv:
                    result['nacionalidad'] = valor
                elif 'licencia' in classDiv:
                    result['licencia'] = valor
                else:
                    if 'Nombre completo:' in row.get_text():
                        result['nombre'] = valor
                    else:
                        print("Fila no casa categorías conocidas", row)

    except Exception as exc:
        print(f"descargaURLficha: problemas descargando '{urlFicha}': {exc}")
        raise exc

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

import re
from argparse import Namespace
from time import gmtime

import pandas as pd

from Utils.FechaHora import PATRONFECHA
from Utils.Web import creaBrowser, DescargaPagina, getObjID

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']

CLAVESDICT = ['id', 'URL', 'alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia',
              'primPartidoT', 'ultPartidoT', 'ultPartidoP']

TRADPOSICION = {'Alero': 'A', 'Escolta': 'E', 'Base': 'B', 'Pívot': 'P', 'Ala-pívot': 'AP', '': '?'}


class FichaJugador():
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', None)
        self.URL = kwargs.get('URL', None)
        self.timestamp = kwargs.get('timestamp', None)
        self.alias = kwargs.get('alias', None)
        self.nombre = kwargs.get('nombre', None)
        self.lugarNac = kwargs.get('lugarNac', None)
        self.fechaNac = kwargs.get('fechaNac', None)
        self.posicion = kwargs.get('posicion', None)
        self.altura = kwargs.get('altura', None)
        self.nacionalidad = kwargs.get('nacionalidad', None)
        self.licencia = kwargs.get('licencia', None)

        self.fotos = set()
        self.primPartidoP = None
        self.ultPartidoP = None
        self.primPartidoT = None
        self.ultPartidoT = None
        self.partidos = set()
        self.equipos = set()

        if 'urlFoto' in kwargs:
            self.fotos.add(kwargs['urlFoto'])

    @staticmethod
    def fromURL(urlFicha, home=None, browser=None, config=Namespace()):
        if browser is None:
            browser = creaBrowser(config)

        fichaJug = descargaURLficha(urlFicha, home=home, browser=browser, config=config)

        return FichaJugador(**fichaJug)

    def actualizaFicha(self, home=None, browser=None, config=Namespace()):

        changes = False

        if browser is None:
            browser = creaBrowser(config)

        newData = descargaURLficha(self.URL, home=home, browser=browser, config=config)

        for k in CLAVESFICHA:
            if getattr(self,k) != newData[k]:
                changes = True
                setattr(self,k, newData[k])

        if newData['urlFoto'] not in self.fotos:
            changes = True
            self.fotos.add(newData['urlFoto'])

        if changes:
            self.timestamp = newData.get('timestamp', gmtime())

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

        if self.primPartidoT is None:
            self.primPartidoP = partido.url
            self.primPartidoT = partido.fechaPartido
        else:
            if partido.fechaPartido < self.primPartidoT:
                self.primPartidoP = partido.url
                self.primPartidoT = partido.fechaPartido

        if self.ultPartidoT is None:
            self.ultPartidoP = partido.url
            self.ultPartidoT = partido.fechaPartido
        else:
            if partido.fechaPartido > self.ultPartidoT:
                self.ultPartidoP = partido.url
                self.ultPartidoT = partido.fechaPartido
        return True

    def __repr__(self):
        return (f"{self.nombre} ({self.id}) {self.fechaNac.strftime('%Y-%m-%d')} P:[{len(self.partidos)}] "
                f"{self.primPartidoT.strftime('%Y-%m-%d')} -> "
                f"{self.ultPartidoT.strftime('%Y-%m-%d')} ({len(self.equipos)})")

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
            if not hasattr(other, k) or getattr(other,k) is None:
                continue
            if getattr(self,k) is None and getattr(other,k) is not None:
                setattr(self,k, getattr(other,k))
                changes = True
            elif newer and getattr(self,k) != getattr(other,k):
                setattr(self,k, getattr(other,k))
                changes = True

    def dictDatosJugador(self):
        result = {k: getattr(self,k) for k in CLAVESDICT}
        result['numEquipos'] = len(self.equipos)
        result['numPartidos'] = len(self.partidos)
        result['pos'] = TRADPOSICION.get(self.posicion, '**')

        return result


def descargaURLficha(urlFicha, home=None, browser=None, config=Namespace()):
    if browser is None:
        browser = creaBrowser(config)
    try:
        result = dict()
        fichaJug = DescargaPagina(urlFicha, home=home, browser=browser, config=config)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()

        result['id'] = getObjID(urlFicha, 'ver')

        fichaData = fichaJug['data']

        cosasUtiles = fichaData.find(name='div', attrs={'class': 'datos'})

        result['urlFoto'] = cosasUtiles.find('div', attrs={'class': 'foto'}).find('img')['src']
        result['alias'] = cosasUtiles.find('h1').get_text().strip()

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

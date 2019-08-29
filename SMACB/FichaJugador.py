import re
from argparse import Namespace
from time import gmtime, strptime

from Utils.Web import DescargaPagina, ExtraeGetParams, creaBrowser

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']


class FichaJugador(object):
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
        self.temporadas = set()
        self.historico = list()
        self.historico.append((self.timestamp, "%s (%s): Carga inicial" % (self.alias, self.id)))

        if 'urlFoto' in kwargs:
            self.fotos.add(kwargs['urlFoto'])

    @staticmethod
    def fromURL(urlFicha, home=None, browser=None, config=Namespace()):
        if browser is None:
            browser = creaBrowser(config)

        fichaJug = descargaURLficha(urlFicha, home=home, browser=browser, config=config)

        return FichaJugador(**fichaJug)

    def actualizaFicha(self, home=None, browser=None, config=Namespace()):
        changes = list()
        subChanges = []

        if browser is None:
            browser = creaBrowser(config)

        newData = descargaURLficha(self.URL, home=home, browser=browser, config=config)

        for k in CLAVESFICHA:
            if self.__getattribute__(k) != newData[k]:
                changes.append((k, self.__getattribute__(k), newData[k]))
                self.__setattr__(k, newData[k])
        if changes:
            subChanges = ["'%s':'%s'->'%s'" % (k, oldV, newV) for k, oldV, newV in changes]

        if newData['urlFoto'] not in self.fotos:
            self.fotos.add(newData['urlFoto'])
            subChanges.append("New foto")

        if subChanges:
            self.timestamp = newData['timestamp']
            self.historico.append((self.timestamp, "%s (%s): %s" % (self.alias, self.id, ','.join(subChanges))))

    def nuevoPartido(self, partido):
        """
        Actualiza información relativa a partidos jugados
        :param partido: OBJETO partido
        :return: Si ha cambiado el objeto o no
        """
        if partido.url in self.partidos:
            return False

        self.partidos.add(partido.url)
        if self.primPartidoT is None:
            self.primPartidoP = partido.url
            self.primPartidoT = partido.timestamp
        else:
            if partido.timestamp < self.primPartidoT:
                self.primPartidoP = partido.url
                self.primPartidoT = partido.timestamp

        if self.ultPartidoT is None:
            self.ultPartidoP = partido.url
            self.ultPartidoT = partido.timestamp
        else:
            if partido.timestamp > self.ultPartidoT:
                self.ultPartidoP = partido.url
                self.ultPartidoT = partido.timestamp
        return True


def descargaURLficha(urlFicha, home=None, browser=None, config=Namespace()):
    if browser is None:
        browser = creaBrowser(config)
    try:
        result = dict()
        fichaJug = DescargaPagina(urlFicha, home=home, browser=browser, config=config)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()

        result['id'] = ExtraeGetParams(urlFicha)['id']

        fichaData = fichaJug['data']
        cosasUtiles = fichaData.find(name='div', attrs={'id': 'portada'})
        result['urlFoto'] = cosasUtiles.find('div', attrs={'id': 'portadafoto'}).find('img')['src']
        result['alias'] = cosasUtiles.find('div', attrs={'id': 'portadadertop'}).text

        tabla = cosasUtiles.find('table')

        for row in tabla.findAll('tr'):
            # print("++++++++++++++ ",row)
            if row.find(name='td', attrs={'class': 'titulojug'}):
                claves = row.find(name='td', attrs={'class': 'titulojug'}).text.strip()
                valores = row.find(name='td', attrs={'class': 'datojug'}).text.strip()
            else:
                continue

            if 'nombre' in claves:
                result['nombre'] = valores
            elif 'lugar' in claves:
                RElugarYfecha = r'^\s*(.*),\s*(\d{2}/\d{2}/\d{4})\s*$'
                reProc = re.match(RElugarYfecha, valores)
                if reProc:
                    if reProc.group(1):
                        result['lugarNac'] = reProc.group(1)
                    if reProc.group(2):
                        result['fechaNac'] = strptime(reProc.group(2), "%d/%m/%Y")
            elif 'altura' in claves:
                aux = valores.split('|')
                result['posicion'] = aux[0].strip()
                REaltura = r'^(\d)[,.](\d{2})\s*m$'
                reProc = re.match(REaltura, aux[1].strip())
                if reProc:
                    result['altura'] = 100 * int(reProc.group(1)) + int(reProc.group(2))
            elif 'licencia' in claves:
                aux = valores.split('|')
                result['nacionalidad'] = aux[0].strip()
                result['licencia'] = aux[1].strip()
            else:
                raise ValueError("descargaURLficha: claves desconocidas: %s -> %s" % (claves, valores))
    except Exception as exc:
        print("descargaURLficha: problemas descargando '%s': %s" % (urlFicha, exc))
        raise exc

    return result

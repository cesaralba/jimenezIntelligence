import re
from time import gmtime, strptime

from Utils.Web import DescargaPagina, ExtraeGetParams

# result['URL'] = urlFicha
# result['timestamp'] = gmtime()
# result['id'] = ExtraeGetParams(urlFicha)['id']
# result['alias'] = cosasUtiles.find('div', attrs={'id': 'portadadertop'}).text
# result['nombre'] = valores
# result['lugarNac'] = reProc.group(1)
# result['fechaNac'] = strptime(reProc.group(2), "%d/%m/%Y")
# result['posicion'] = aux[0].strip()
# result['altura'] = 100 * int(reProc.group(1)) + int(reProc.group(2))
# result['nacionalidad'] = aux[0].strip()
# result['licencia'] = aux[1].strip()
# result['urlFoto'] = cosasUtiles.find('div', attrs={'id': 'portadafoto'}).find('img')['src']

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']


class FichaJugador(object):
    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.URL = kwargs['URL']
        self.timestamp = kwargs['timestamp']
        self.alias = kwargs['alias']
        self.nombre = kwargs['nombre']
        self.lugarNac = kwargs['lugarNac']
        self.fechaNac = kwargs['fechaNac']
        self.posicion = kwargs['posicion']
        self.altura = kwargs['altura']
        self.nacionalidad = kwargs['nacionalidad']
        self.licencia = kwargs['licencia']

        self.fotos = set()
        self.primPartido = None
        self.ultPartido = None
        self.partidos = set()
        self.temporadas = set()
        self.historico = list()
        self.historico.append((self.timestamp, "%s (%s): Carga inicial" % (self.alias, self.id)))

        if 'urlFoto' in kwargs:
            self.fotos.add(kwargs['urlFoto'])

    @staticmethod
    def fromURL(urlFicha, home=None, browser=None, config={}):
        fichaJug = DescargaPagina(urlFicha, home=home, browser=browser, config=config)

        return FichaJugador(**fichaJug)

    def actualizaFicha(self, home=None, browser=None, config={}):
        changes = list()
        subChanges = []
        newData = DescargaPagina(self.URL, home=home, browser=browser, config=config)

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
            self.historico.append(self.timestamp, "%s (%s): %s" % (self.alias, self.id, ','.join(subChanges)))


def descargaURLficha(urlFicha, home=None, browser=None, config={}):
    result = dict()
    result['URL'] = urlFicha
    result['timestamp'] = gmtime()
    fichaJug = DescargaPagina(urlFicha, home=home, browser=browser, config=config)

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
            result['lugarNac'] = reProc.group(1)
            result['fechaNac'] = strptime(reProc.group(2), "%d/%m/%Y")
        elif 'altura' in claves:
            aux = valores.split('|')
            result['posicion'] = aux[0].strip()
            REaltura = r'^(\d)[,.](\d{2})\s*m$'
            reProc = re.match(REaltura, aux[1].strip())
            result['altura'] = 100 * int(reProc.group(1)) + int(reProc.group(2))
        elif 'licencia' in claves:
            aux = valores.split('|')
            result['nacionalidad'] = aux[0].strip()
            result['licencia'] = aux[1].strip()
        else:
            raise ValueError("descargaURLficha: claves desconocidas: %s -> %s" % (claves, valores))

    return result

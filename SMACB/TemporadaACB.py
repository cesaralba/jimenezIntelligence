'''
Created on Jan 4, 2018

@author: calba
'''

from collections import defaultdict
from pickle import dump, load
from time import gmtime

from SMACB.CalendarioACB import CalendarioACB, calendario_URLBASE
from SMACB.PartidoACB import PartidoACB


class TemporadaACB(object):

    '''
    Aglutina calendario y lista de partidos
    '''

    def __init__(self, competition="LACB", edition=None, urlbase=calendario_URLBASE):
        self.timestamp = gmtime()
        self.Calendario = CalendarioACB(competition=competition, edition=edition, urlbase=urlbase)
        self.PartidosDescargados = set()
        self.Partidos = dict()

    def actualizaTemporada(self, home=None, browser=None, config={}):
        self.Calendario.bajaCalendario(browser=browser, config=config)

        partidosBajados = set()

        for partido in self.Calendario.Partidos:
            if partido in self.PartidosDescargados:
                continue

            nuevoPartido = PartidoACB(**(self.Calendario.Partidos[partido]))
            nuevoPartido.DescargaPartido(home=None, browser=browser, config=config)

            self.PartidosDescargados.add(partido)
            self.Partidos[partido] = nuevoPartido
            partidosBajados.add(partido)

            if config.justone:  # Just downloads a game (for testing/dev purposes)
                break

        if partidosBajados:
            self.timestamp = gmtime()

        return partidosBajados

    def grabaTemporada(self, filename):

        # TODO: Protect this
        # TODO: Ver por qué graba bs4 y cosas así
        dump(self, open(filename, "wb"))

    def cargaTemporada(self, filename):
        # TODO: Protect this
        aux = load(open(filename, "rb"))

        for key in aux.__dict__.keys():
            self.__setattr__(key, aux.__getattribute__(key))

    def listaJugadores(self, jornada=0, jornadaMax=0, fechaMax=None):

        def SacaJugadoresPartido(partido):
            for codigo in partido.Jugadores:
                (resultado['codigo2nombre'][codigo]).add(partido.Jugadores[codigo]['nombre'])
                resultado['nombre2codigo'][partido.Jugadores[codigo]['nombre']] = codigo

        resultado = {'codigo2nombre': defaultdict(set), 'nombre2codigo': dict()}

        for partido in self.Partidos:
            aceptaPartido = False
            if jornada and self.Partidos[partido].Jornada == jornada:
                aceptaPartido = True
            elif jornadaMax and self.Partidos[partido].Jornada >= jornadaMax:
                aceptaPartido = True
            elif fechaMax and self.Partidos[partido].FechaHora < fechaMax:
                aceptaPartido = True
            else:
                aceptaPartido = True

            if aceptaPartido:
                SacaJugadoresPartido(self.Partidos[partido])

        return resultado

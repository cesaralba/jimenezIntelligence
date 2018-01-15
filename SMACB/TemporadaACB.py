'''
Created on Jan 4, 2018

@author: calba
'''

from collections import defaultdict
from copy import copy
from pickle import dump, load
from time import gmtime, strftime

from SMACB.CalendarioACB import CalendarioACB, calendario_URLBASE
from SMACB.PartidoACB import PartidoACB
from Utils.Misc import FORMATOtimestamp


class TemporadaACB(object):

    '''
    Aglutina calendario y lista de partidos
    '''

    def __init__(self, competition="LACB", edition=None, urlbase=calendario_URLBASE):
        self.timestamp = gmtime()
        self.Calendario = CalendarioACB(competition=competition, edition=edition, urlbase=urlbase)
        self.PartidosDescargados = set()
        self.Partidos = dict()
        self.changed = False

    def actualizaTemporada(self, home=None, browser=None, config={}):
        self.Calendario.bajaCalendario(browser=browser, config=config)

        partidosBajados = set()

        for partido in self.Calendario.Partidos:
            if partido in self.PartidosDescargados:
                continue

            nuevoPartido = PartidoACB(**(self.Calendario.Partidos[partido]))
            nuevoPartido.descargaPartido(home=home, browser=browser, config=config)

            self.PartidosDescargados.add(partido)
            self.Partidos[partido] = nuevoPartido
            self.actualizaNombresEquipo(nuevoPartido)
            partidosBajados.add(partido)

            if config.justone:  # Just downloads a game (for testing/dev purposes)
                break

        if partidosBajados:
            self.changed = True
            self.timestamp = gmtime()

        return partidosBajados

    def actualizaNombresEquipo(self, partido):
        for loc in partido.Equipos:
            nombrePartido = partido.Equipos[loc]['Nombre']
            codigoParam = partido.CodigosCalendario[loc]
            if self.Calendario.nuevaTraduccionEquipo2Codigo(nombrePartido, codigoParam):
                self.changed = True

    def grabaTemporada(self, filename):
        aux = copy(self)

        # Clean stuff that shouldn't be saved
        for atributo in ('changed'):
            if hasattr(aux, atributo):
                aux.__delattr__(atributo)

        # TODO: Protect this
        # TODO: Ver por qué graba bs4 y cosas así
        dump(aux, open(filename, "wb"))

    def cargaTemporada(self, filename):
        # TODO: Protect this
        aux = load(open(filename, "rb"))

        for atributo in aux.__dict__.keys():
            if atributo in ('changed'):
                continue
            self.__setattr__(atributo, aux.__getattribute__(atributo))

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

    def resumen(self):
        print(self.__dict__.keys())
        print("Temporada. Timestamp %s" % strftime(FORMATOtimestamp, self.timestamp))
        print("Temporada. Cambios %s" % self.changed)
        print(self.Calendario.__dict__.keys())
        print("Temporada. Partidos cargados: %i,%i" % (len(self.Partidos), len(self.PartidosDescargados)))
        for partidoID in self.Partidos:
            partido = self.Partidos[partidoID]
            resumenPartido = " * %s: %s (%s) %i - %i %s (%s) " % (partidoID, partido.EquiposCalendario['Local'],
                                                                  partido.CodigosCalendario['Local'],
                                                                  partido.ResultadoCalendario['Local'],
                                                                  partido.ResultadoCalendario['Visitante'],
                                                                  partido.EquiposCalendario['Visitante'],
                                                                  partido.CodigosCalendario['Visitante'])

            print(resumenPartido)

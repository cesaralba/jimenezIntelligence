'''
Created on Jan 4, 2018

@author: calba
'''

from argparse import Namespace
from collections import defaultdict
from copy import copy
from pickle import dump, load
from sys import exc_info, setrecursionlimit
from time import gmtime, strftime
from traceback import print_exception
from typing import Iterable

import numpy as np
import pandas as pd

from Utils.FechaHora import fechaParametro2pddatetime
from Utils.Pandas import combinaPDindexes
from Utils.Web import creaBrowser
from .CalendarioACB import calendario_URLBASE, CalendarioACB, URL_BASE
from .Constants import OtherLoc, EqRival, OtherTeam, LOCALNAMES, LocalVisitante
from .FichaJugador import FichaJugador
from .PartidoACB import PartidoACB
from .PlantillaACB import descargaPlantillasCabecera, PlantillaACB

COLSESTADSASCENDING = [
    ('Info', 'prorrogas', 'mean'),
    ('Info', 'prorrogas', 'sum'),
    ('Eq', 'BP', 'mean'),
    ('Eq', 'BP', 'min'),
    ('Eq', 'BP', 'median'),
    ('Eq', 'BP', 'max'),
    ('Eq', 'BP', 'sum'),
    ('Eq', 'TAP-C', 'mean'),
    ('Eq', 'TAP-C', 'min'),
    ('Eq', 'TAP-C', 'median'),
    ('Eq', 'TAP-C', 'max'),
    ('Eq', 'TAP-C', 'sum'),
    ('Eq', 'FP-C', 'mean'),
    ('Eq', 'FP-C', 'min'),
    ('Eq', 'FP-C', 'median'),
    ('Eq', 'FP-C', 'max'),
    ('Eq', 'FP-C', 'sum'),
    ('Eq', 'PNR', 'mean'),
    ('Eq', 'PNR', 'min'),
    ('Eq', 'PNR', 'median'),
    ('Eq', 'PNR', 'max'),
    ('Eq', 'PNR', 'sum'),

    ('Rival', 'P', 'mean'),
    ('Rival', 'P', 'std'),
    ('Rival', 'P', 'min'),
    ('Rival', 'P', 'median'),
    ('Rival', 'P', 'max'),
    ('Rival', 'P', 'sum'),
    ('Rival', 'OER', 'mean'),
    ('Rival', 'OER', 'min'),
    ('Rival', 'OER', 'median'),
    ('Rival', 'OER', 'max'),
    ('Rival', 'OER', 'sum'),
    ('Rival', 'OERpot', 'mean'),
    ('Rival', 'OERpot', 'min'),
    ('Rival', 'OERpot', 'median'),
    ('Rival', 'OERpot', 'max'),
    ('Rival', 'OERpot', 'sum'),
]

DEFAULTNAVALUES = {
    ('Eq', 'convocados', 'sum'): 0,
    ('Eq', 'utilizados', 'sum'): 0,
    ('Info', 'prorrogas', 'count'): 0,
    ('Info', 'prorrogas', 'max'): 0,
    ('Info', 'prorrogas', 'mean'): 0,
    ('Info', 'prorrogas', 'median'): 0,
    ('Info', 'prorrogas', 'min'): 0,
    ('Info', 'prorrogas', 'std'): 0,
    ('Info', 'prorrogas', 'sum'): 0,
    ('Rival', 'convocados', 'sum'): 0,
    ('Rival', 'utilizados', 'sum'): 0,
}

class TemporadaACB(object):
    '''
    Aglutina calendario y lista de partidos
    '''

    # TODO: función __str__

    def __init__(self, **kwargs):
        self.competicion = kwargs.get('competicion', "LACB")
        self.edicion = kwargs.get('edicion', None)
        self.urlbase = kwargs.get('urlbase', calendario_URLBASE)
        descargaFichas = kwargs.get('descargaFichas', False)
        descargaPlantillas = kwargs.get('descargaPlantillas', False)

        self.timestamp = gmtime()
        self.Calendario = CalendarioACB(competicion=self.competicion, edicion=self.edicion, urlbase=self.urlbase)
        self.Partidos = dict()
        self.changed = False
        self.tradJugadores = {'id2nombres': defaultdict(set), 'nombre2ids': defaultdict(set)}
        self.descargaFichas = descargaFichas
        self.descargaPlantillas = descargaPlantillas
        self.fichaJugadores = dict()
        self.fichaEntrenadores = dict()
        self.plantillas = dict()

    def __repr__(self):
        tstampStr = strftime("%Y%m%d-%H:%M:%S",self.timestamp)
        result = f"{self.competicion} Temporada: {self.edicion} Datos: {tstampStr}"
        return result

    def actualizaTemporada(self, home=None, browser=None, config=Namespace()):
        changeOrig = self.changed

        config = Namespace(**config) if isinstance(config, dict) else config

        if browser is None:
            browser = creaBrowser(config)
            browser.open(URL_BASE)

        self.Calendario.actualizaCalendario(browser=browser, config=config)
        self.actualizaPlantillas(browser=browser, config=config)

        if 'procesabio' in config and config.procesaBio:
            self.descargaFichas = True

        partidosBajados = set()

        for partido in set(self.Calendario.Partidos.keys()).difference(set(self.Partidos.keys())):
            try:
                nuevoPartido = PartidoACB(**(self.Calendario.Partidos[partido]))
                nuevoPartido.descargaPartido(home=home, browser=browser, config=config)
                self.Partidos[partido] = nuevoPartido

                self.actualizaInfoAuxiliar(nuevoPartido, browser, config)

                partidosBajados.add(partido)

            except KeyboardInterrupt:
                print("actualizaTemporada: Ejecución terminada por el usuario")
                break
            except BaseException:
                print("actualizaTemporada: problemas descargando  partido '%s': %s" % (partido, exc_info()))
                print_exception(*exc_info())

            if 'justone' in config and config.justone:  # Just downloads a game (for testing/dev purposes)
                break

        self.changed = self.changed | (len(partidosBajados) > 0)

        if self.changed != changeOrig:
            self.timestamp = gmtime()

        return partidosBajados

    def actualizaInfoAuxiliar(self, nuevoPartido, browser, config):
        self.actualizaNombresEquipo(nuevoPartido)
        if self.descargaFichas:
            self.actualizaFichasPartido(nuevoPartido, browser=browser, config=config)
        self.actualizaTraduccionesJugador(nuevoPartido)
        # Añade la información de equipos de partido a traducciones de equipo.
        # (el código de equipo ya no viene en el calendario)
        for eqData in nuevoPartido.Equipos.values():
            self.Calendario.nuevaTraduccionEquipo2Codigo(nombres=eqData['Nombre'], abrev=eqData['abrev'],
                                                         id=eqData['id'])

    def actualizaNombresEquipo(self, partido):
        for loc in partido.Equipos:
            nombrePartido = partido.Equipos[loc]['Nombre']
            codigoParam = partido.Equipos[loc]['abrev']
            idParam = partido.Equipos[loc]['id']
            if self.Calendario.nuevaTraduccionEquipo2Codigo(nombrePartido, codigoParam, idParam):
                self.changed = True

    def grabaTemporada(self, filename):
        aux = copy(self)

        # Clean stuff that shouldn't be saved
        for atributo in ('changed'):
            if hasattr(aux, atributo):
                aux.__delattr__(atributo)

        setrecursionlimit(50000)
        # TODO: Protect this
        dump(aux, open(filename, "wb"))

    def cargaTemporada(self, filename):
        # TODO: Protect this
        aux = load(open(filename, "rb"))

        for atributo in aux.__dict__.keys():
            if atributo in ('changed'):
                continue
            self.__setattr__(atributo, aux.__getattribute__(atributo))

    def actualizaFichasPartido(self, nuevoPartido, browser=None, config=Namespace(), refrescaFichas=False):
        if browser is None:
            browser = creaBrowser(config)
            browser.open(URL_BASE)

        for codJ, datosJug in nuevoPartido.Jugadores.items():
            if codJ not in self.fichaJugadores:
                nuevaFicha = FichaJugador.fromURL(datosJug['linkPersona'], home=browser.get_url(), browser=browser,
                                                  config=config)
                self.fichaJugadores[codJ] = nuevaFicha

            elif refrescaFichas:
                self.fichaJugadores[codJ] = self.fichaJugadores[codJ].actualizaFicha(browser=browser, config=config)

            self.changed |= self.fichaJugadores[codJ].nuevoPartido(nuevoPartido)

        # TODO: Procesar ficha de entrenadores
        for codE in nuevoPartido.Entrenadores:
            pass

    def actualizaPlantillas(self, browser=None, config=Namespace()):
        if self.descargaPlantillas:
            if browser is None:
                browser = creaBrowser(config)
                browser.open(URL_BASE)

            if len(self.plantillas):  # Ya se han descargado por primera vez
                changes = [self.plantillas[id].descargaYactualizaPlantilla(browser=None, config=Namespace()) for id in self.plantillas]
                self.changed |= any(changes)
            else:
                datosPlantillas = descargaPlantillasCabecera(browser, config)
                for id, datos in datosPlantillas.items():
                    self.plantillas[id] = PlantillaACB(id)
                    self.plantillas[id].actualizaPlantillaDescargada(datos)
                self.changed = True

    def actualizaTraduccionesJugador(self, nuevoPartido):
        for codJ, datosJug in nuevoPartido.Jugadores.items():
            if codJ in self.fichaJugadores:
                ficha = self.fichaJugadores[codJ]

                self.tradJugadores['nombre2ids'][ficha.nombre].add(ficha.id)
                self.tradJugadores['nombre2ids'][ficha.alias].add(ficha.id)
                self.tradJugadores['id2nombres'][ficha.id].add(ficha.nombre)
                self.tradJugadores['id2nombres'][ficha.id].add(ficha.alias)

            self.tradJugadores['nombre2ids'][datosJug['nombre']].add(datosJug['codigo'])
            self.tradJugadores['id2nombres'][datosJug['codigo']].add(datosJug['nombre'])

    def extraeDataframeJugadores(self, listaURLPartidos=None):

        def jorFech2periodo(dfTemp):
            periodoAct = 0
            jornada = dict()
            claveMin = dict()
            claveMax = dict()
            curVal = None
            jf2periodo = defaultdict(lambda: defaultdict(int))

            dfPairs = dfTemp.apply(lambda r: (r['fechaPartido'].date(), r['jornada']), axis=1).unique()
            for p in sorted(list(dfPairs)):
                if curVal is None or curVal[1] != p[1]:
                    if curVal:
                        periodoAct += 1

                    curVal = p
                    jornada[periodoAct] = p[1]
                    claveMin[periodoAct] = p[0]
                    claveMax[periodoAct] = p[0]

                else:
                    claveMax[periodoAct] = p[0]
                jf2periodo[p[1]][p[0]] = periodoAct

            p2k = {p: (("%s" % claveMin[p]) + (("\na %s" % claveMax[p]) if (claveMin[p] != claveMax[p]) else "") + (
                    "\n(J:%2i)" % jornada[p])) for p in jornada}

            result = dict()
            for j in jf2periodo:
                result[j] = dict()
                for d in jf2periodo[j]:
                    result[j][d] = p2k[jf2periodo[j][d]]

            return result

        listaURLs = listaURLPartidos or self.Partidos.keys()

        dfPartidos = [self.Partidos[pURL].jugadoresAdataframe() for pURL in listaURLs]

        dfResult = pd.concat(dfPartidos, axis=0, ignore_index=True, sort=True)

        periodos = jorFech2periodo(dfResult)

        dfResult['periodo'] = dfResult.apply(lambda r: periodos[r['jornada']][r['fechaPartido'].date()], axis=1)

        return (dfResult)

    def dfEstadsJugadores(self, dfDatosPartidos: pd.DataFrame, abrEq: str = None):
        COLDROPPER = ['jornada', 'temporada']
        COLSIDENT = ['competicion', 'temporada', 'codigo', 'dorsal', 'nombre', 'CODequipo', 'IDequipo']

        if abrEq:
            abrevsEq = self.Calendario.abrevsEquipo(abrEq)

            estadsJugadoresEq = dfDatosPartidos.loc[dfDatosPartidos['CODequipo'].isin(abrevsEq)]
        else:
            estadsJugadoresEq = dfDatosPartidos

        auxEstadisticosDF = estadsJugadoresEq.drop(columns=COLDROPPER).groupby('codigo').apply(
            auxCalculaEstadsSubDataframe)

        # Ajusta la suma de los porcentajes a la media de las sumas
        for k in '123C':
            kI = f'T{k}-I'
            kC = f'T{k}-C'
            kRes = f'T{k}%'
            auxEstadisticosDF[kRes, 'sum'] = auxEstadisticosDF[kC, 'sum'] / auxEstadisticosDF[kI, 'sum'] * 100.0
        auxEstadisticosDF['ppTC', 'sum'] = auxEstadisticosDF['PTC', 'sum'] / auxEstadisticosDF['TC-I', 'sum']

        auxIdentsDF = estadsJugadoresEq[COLSIDENT].groupby('codigo').tail(n=1).set_index('codigo', drop=False)
        auxIdentsDF.columns = pd.MultiIndex.from_tuples([('Jugador', col) for col in auxIdentsDF.columns])

        result = pd.concat([auxIdentsDF, auxEstadisticosDF], axis=1)
        return result

    def sigPartido(self, abrEq) -> (dict, tuple, list, list, list, list, bool):
        """
        Devuelve el siguiente partido de un equipo y los anteriores y siguientes del equipo y su próximo rival
        :param abrEq: abreviatura del equipo objetivo
        :return: tupla con los siguientes valores
        * Información del siguiente partido
        * Tupla con las abrevs del equipo local y visit del siguiente
        * Partidos pasados del eq local
        * Partidos futuros del eq local
        * Partidos pasados del eq visitante
        * Partidos futuros del eq visitante
        * Si la abrev objetivo es local (True) o visit (False)
        """
        juCal, peCal = self.Calendario.partidosEquipo(abrEq)
        peOrd = sorted([p for p in peCal], key=lambda x: x['fechaPartido'])

        juOrdTem = sorted([self.Partidos[p['url']] for p in juCal], key=lambda x: x.fechaPartido)

        sigPart = peOrd.pop(0)
        abrevsEq = self.Calendario.abrevsEquipo(abrEq)
        abrRival = sigPart['participantes'].difference(abrevsEq).pop()
        juRivCal, peRivCal = self.Calendario.partidosEquipo(abrRival)

        peRivOrd = sorted([p for p in peRivCal if p['jornada'] != sigPart['jornada']], key=lambda x: x['fechaPartido'])
        juRivTem = sorted([self.Partidos[p['url']] for p in juRivCal], key=lambda x: x.fechaPartido)

        eqIsLocal = sigPart['loc2abrev']['Local'] in abrevsEq
        juIzda, peIzda, juDcha, peDcha = (juOrdTem, peOrd, juRivTem, peRivOrd) if eqIsLocal else (
            juRivTem, peRivOrd, juOrdTem, peOrd)
        resAbrevs = (abrEq, abrRival) if eqIsLocal else (abrRival, abrEq)

        return sigPart, resAbrevs, juIzda, peIzda, juDcha, peDcha, eqIsLocal

    def clasifEquipo(self, abrEq, fecha=None):
        abrevsEq = self.Calendario.abrevsEquipo(abrEq)
        juCal, _ = self.Calendario.partidosEquipo(abrEq)
        result = defaultdict(int)
        result['Lfav'] = list()
        result['Lcon'] = list()
        result['Jjug'] = set()
        result['CasaFuera'] = {'Local': defaultdict(int), 'Visitante': defaultdict(int)}

        partidosAcontar = [p for p in juCal if self.Partidos[p['url']].fechaPartido < fecha] if fecha else juCal

        for datosCal in partidosAcontar:
            result['Jjug'].add(int(datosCal['jornada']))

            abrevUsada = abrevsEq.intersection(datosCal['participantes']).pop()
            locEq = datosCal['abrev2loc'][abrevUsada]
            locRival = OtherLoc(locEq)

            datosEq = datosCal['equipos'][locEq]
            datosRival = datosCal['equipos'][locRival]
            claveRes = 'V' if datosEq['haGanado'] else 'D'

            result['Jug'] += 1
            result[claveRes] += 1
            result['CasaFuera'][locEq][claveRes] += 1

            result['Pfav'] += datosEq['puntos']
            result['Lfav'].append(datosEq['puntos'])

            result['Pcon'] += datosRival['puntos']
            result['Lcon'].append(datosRival['puntos'])

        result['idEq'] = self.Calendario.tradEquipos['c2i'][abrEq]
        result['nombresEq'] = self.Calendario.tradEquipos['c2n'][abrEq]
        result['abrevsEq'] = abrevsEq

        return result

    def clasifLiga(self, fecha=None):
        result = sorted([self.clasifEquipo(list(cSet)[0], fecha=fecha)
                         for cSet in self.Calendario.tradEquipos['i2c'].values()],
                        key=lambda x: entradaClas2k(x), reverse=True)

        return result

    def dataFrameFichasJugadores(self):
        auxdict = {id: ficha.dictDatosJugador() for id, ficha in self.fichaJugadores.items()}

        for id, ficha in auxdict.items():
            partido = self.Partidos[ficha['ultPartidoP']]
            entradaJug = partido.Jugadores[id]
            auxdict[id]['ultEquipo'] = entradaJug['equipo']
            auxdict[id]['ultEquipoAbr'] = entradaJug['CODequipo']

        auxDF = pd.DataFrame.from_dict(auxdict, orient='index')
        for col in ['fechaNac', 'primPartidoT', 'ultPartidoT']:
            auxDF[col] = pd.to_datetime(auxDF[col])  # TODO: Esto no era

        return auxDF

    def dataFramePartidosLV(self, listaAbrevEquipos: Iterable[str] = None, fecha=None):
        """
        Genera un dataframe LV con los partidos de uno o más equipos hasta determinada fecha
        :param listaAbrevEquipos: si None, son todos los partidos
        :param fecha: si None son todos los partidos (límite duro < )
        :return:
        """

        partidosAprocesar_url = list()
        # Genera la lista de partidos a incluir
        if listaAbrevEquipos:
            # Recupera la lista de abreviaturas que de los equipos que puede cambiar (la abrev del equipo)
            # a lo largo de la temporada
            colAbrevList = [self.Calendario.abrevsEquipo(ab) for ab in listaAbrevEquipos]
            colAbrevSet = set()
            for abrSet in colAbrevList:
                colAbrevSet.update(abrSet)

            # Crea la lista de partidos de aquellos en los que están las abreviaturas
            for pURL, pData in self.Partidos.items():
                if colAbrevSet.intersection(pData.CodigosCalendario.values()):
                    partidosAprocesar_url.append(pURL)
        else:
            partidosAprocesar_url = self.Partidos.keys()

        if fecha:
            fecha_formatted = fechaParametro2pddatetime(fecha)
            partidos_DFlist = [self.Partidos[pURL].partidoAdataframe() for pURL in partidosAprocesar_url if
                               self.Partidos[pURL].fechaPartido < fecha_formatted]
        else:
            partidos_DFlist = [self.Partidos[pURL].partidoAdataframe() for pURL in partidosAprocesar_url]

        result = pd.concat(partidos_DFlist)
        return result

    def dfPartidosLV2ER(self, partidos: pd.DataFrame, abrEq: str = None):
        COLSINFO = ['jornada', 'fechaPartido', 'Pabellon', 'Asistencia', 'prorrogas', 'url', 'competicion', 'temporada',
                    'idPartido', 'Ptot', 'POStot']

        finalDFlist = []

        if abrEq:
            idEq = list(self.Calendario.tradEquipos['c2i'][abrEq])[0]
            partidosEq = partidos.loc[(partidos['Local', 'id'] == idEq) | (partidos['Visitante', 'id'] == idEq)]

            for esLocal in [True, False]:
                tagEq, tagRival = ('Local', 'Visitante') if esLocal else ('Visitante', 'Local')

                auxDFlocal = partidosEq.loc[(partidosEq['Local', 'id'] == idEq) == esLocal]
                infoDF = auxDFlocal['Info'][COLSINFO]
                eqDF = auxDFlocal[tagEq]
                rivalDF = auxDFlocal[tagRival]

                auxDF = pd.concat([infoDF, eqDF, rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
                finalDFlist.append(auxDF)
        else:
            for loc in LocalVisitante:
                infoDF = partidos['Info'][COLSINFO]
                eqDF = partidos[loc]
                rivalDF = partidos[OtherLoc(loc)]

                auxDF = pd.concat([infoDF, eqDF, rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
                finalDFlist.append(auxDF)

        result = pd.concat(finalDFlist)

        return result.sort_values(by=('Info', 'fechaPartido'))

    def dfEstadsEquipo(self, dfEstadsPartidosEq: pd.DataFrame, abrEq: str = None):
        colProrrogas = ('Info', 'prorrogas')
        COLDROPPER = [('Info', 'jornada')]

        if abrEq:
            abrevsEq = self.Calendario.abrevsEquipo(abrEq)

            estadPartidos = dfEstadsPartidosEq.loc[dfEstadsPartidosEq[('Eq', 'abrev')].isin(abrevsEq)]
        else:
            estadPartidos = dfEstadsPartidosEq

        resultSinProrogas = auxCalculaEstadsSubDataframe(estadPartidos.drop(columns=(COLDROPPER + [colProrrogas])))

        # Sólo cuenta prórrogas de partidos donde ha habido
        if estadPartidos[colProrrogas].sum() != 0:
            datosProrrogas = estadPartidos.loc[estadPartidos[colProrrogas] != 0][[colProrrogas]]
            estadProrrogas = auxCalculaEstadsSubDataframe(datosProrrogas)
            result = pd.concat([resultSinProrogas, estadProrrogas])
        else:
            result = resultSinProrogas

        # No tiene sentido sumar convocados y usados.
        # TODO: Podría tener sentido calcular jugadores únicos pero es trabajoso
        for eq in EqRival:
            for col in [(eq, 'convocados', 'sum'), (eq, 'utilizados', 'sum')]:
                result[col] = np.nan
        # Calculate sum field for ratios as the ratio of sum fields. Shooting percentages
        for k in '123C':
            kI = f'T{k}-I'
            kC = f'T{k}-C'
            kRes = f'T{k}%'
            for eq in EqRival:
                result[(eq, kRes, 'sum')] = result[(eq, kC, 'sum')] / result[
                    (eq, kI, 'sum')] * 100.0
        # Calculate sum field for ratios as the ratio of sum fields. Other ratios
        for eq in EqRival:
            for k in '23':
                result[(eq, f't{k}/tc-I', 'sum')] = result[(eq, f'T{k}-I', 'sum')] / result[(eq, 'TC-I', 'sum')] * 100.0
                result[(eq, f't{k}/tc-C', 'sum')] = result[(eq, f'T{k}-C', 'sum')] / result[(eq, 'TC-C', 'sum')] * 100.0
                result[(eq, f'eff-t{k}', 'sum')] = result[(eq, f'T{k}-C', 'sum')] * int(k) / (
                        result[(eq, 'T2-C', 'sum')] * 2 + result[(eq, 'T3-C', 'sum')] * 3) * 100.0
            result[(eq, 'A/TC-C', 'sum')] = result[(eq, 'A', 'sum')] / result[(eq, 'TC-C', 'sum')] * 100.0
            result[(eq, 'A/BP', 'sum')] = result[(eq, 'A', 'sum')] / result[(eq, 'BP', 'sum')]
            result[(eq, 'RO/TC-F', 'sum')] = result[(eq, 'R-O', 'sum')] / (
                    result[(eq, 'TC-I', 'sum')] - result[(eq, 'TC-C', 'sum')]) * 100.0
            result[(eq, 'ppTC', 'sum')] = (result[(eq, 'T2-C', 'sum')] * 2 + result[(eq, 'T3-C', 'sum')] * 3) / (
                    result[(eq, 'T2-I', 'sum')] + result[(eq, 'T3-I', 'sum')])
            result[(eq, 'OER', 'sum')] = result[(eq, 'P', 'sum')] / result[(eq, 'POS', 'sum')]
            result[(eq, 'OERpot', 'sum')] = result[(eq, 'P', 'sum')] / (
                    result[(eq, 'POS', 'sum')] - result[(eq, 'BP', 'sum')])
            result[(eq, 'EffRebD', 'sum')] = result[(eq, 'R-D', 'sum')] / (
                    result[(eq, 'R-D', 'sum')] + result[(OtherTeam(eq), 'R-O', 'sum')])
            result[(eq, 'EffRebO', 'sum')] = result[(eq, 'R-O', 'sum')] / (
                    result[(eq, 'R-O', 'sum')] + result[(OtherTeam(eq), 'R-D', 'sum')])

        return result

    def dfEstadsLiga(self, fecha=None):

        resultDict = dict()
        # Todos los partidos de la liga hasta fecha
        dfTodosPartidos = self.dataFramePartidosLV(fecha)

        for idEq in self.Calendario.tradEquipos[
            'i2c'].values():  # Se usa id porque es único para equipos y la abr puede cambiar
            abrevEq = next(iter(idEq))  # Coge una abr cualquiera que corresponda al id. (se usa
            # abrev porque esas son fáciles de asociar a equipos)
            dfPartidosEq = self.dfPartidosLV2ER(dfTodosPartidos, abrevEq)
            dfEstadsAgrEq = self.dfEstadsEquipo(dfPartidosEq, abrEq=abrevEq)
            resultDict[abrevEq] = dfEstadsAgrEq
        result = pd.DataFrame.from_dict(data=resultDict, orient='index').sort_index()

        return result


def calculaTempStats(datos, clave, filtroFechas=None):
    if clave not in datos:
        raise KeyError("Clave '%s' no está en datos." % clave)

    datosWrk = datos
    if filtroFechas:  # TODO: Qué hacer con el filtro
        datosWrk = datos

    agg = datosWrk.set_index('codigo')[clave].astype('float64').groupby('codigo').agg(['mean', 'std', 'count',
                                                                                       'median', 'min', 'max',
                                                                                       'skew'])
    agg1 = agg.rename(columns=dict([(x, clave + "-" + x) for x in agg.columns])).reset_index()
    return agg1


def calculaZ(datos, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    finalKeys = ['codigo', 'competicion', 'temporada', 'jornada', 'CODequipo', 'CODrival', 'esLocal',
                 'haJugado', 'fechaPartido', 'periodo', clave]
    finalTypes = {'CODrival': 'category', 'esLocal': 'bool', 'CODequipo': 'category',
                  ('half-' + clave): 'bool', ('aboveAvg-' + clave): 'bool', (clZ + '-' + clave): 'float64'}
    # We already merged SuperManager?
    if 'pos' in datos.columns:
        finalKeys.append('pos')
        finalTypes['pos'] = 'category'

    datosWrk = datos
    if filtroFechas:
        datosWrk = datos  # TODO: filtro de fechas

    agg1 = calculaTempStats(datos, clave, filtroFechas)

    dfResult = datosWrk[finalKeys].merge(agg1)
    stdMult = (1 / dfResult[clave + "-std"]) if useStd else 1
    dfResult[clZ + '-' + clave] = (dfResult[clave] - dfResult[clave + "-mean"]) * stdMult
    dfResult['half-' + clave] = (((dfResult[clave] - dfResult[clave + "-median"]) > 0.0)[~dfResult[clave].isna()]) * 100
    dfResult['aboveAvg-' + clave] = ((dfResult[clZ + '-' + clave] >= 0.0)[~dfResult[clave].isna()]) * 100

    return dfResult.astype(finalTypes)


def calculaVars(temporada, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    combs = {'R': ['CODrival'], 'RL': ['CODrival', 'esLocal'], 'L': ['esLocal']}
    if 'pos' in temporada.columns:
        combs['RP'] = ['CODrival', 'pos']
        combs['RPL'] = ['CODrival', 'esLocal', 'pos']

    colAdpt = {('half-' + clave + '-mean'): (clave + '-mejorMitad'),
               ('aboveAvg-' + clave + '-mean'): (clave + '-sobreMedia')}
    datos = calculaZ(temporada, clave, useStd=useStd, filtroFechas=filtroFechas)
    result = dict()

    for comb in combs:
        combfloat = combs[comb] + [(clZ + '-' + clave)]
        resfloat = datos[combfloat].groupby(combs[comb]).agg(['mean', 'std', 'count', 'min', 'median', 'max', 'skew'])
        combbool = combs[comb] + [('half-' + clave), ('aboveAvg-' + clave)]
        resbool = datos[combbool].groupby(combs[comb]).agg(['mean'])
        result[comb] = pd.concat([resbool, resfloat], axis=1, sort=True).reset_index()
        newColNames = [((comb + "-" + colAdpt.get(x, x)) if clave in x else x)
                       for x in combinaPDindexes(result[comb].columns)]
        result[comb].columns = newColNames
        result[comb]["-".join([comb, clave, (clZ.lower() + "Min")])] = (
                result[comb]["-".join([comb, clZ, clave, 'mean'])] - result[comb]["-".join([comb, clZ, clave, 'std'])])
        result[comb]["-".join([comb, clave, (clZ.lower() + "Max")])] = (
                result[comb]["-".join([comb, clZ, clave, 'mean'])] + result[comb]["-".join([comb, clZ, clave, 'std'])])

    return result


def entradaClas2k(ent: dict) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (ratio Vict/Jugados, Vict, Ventaja/Jugados, Pfavor)
    """

    ratioV = ent.get('V', 0) / ent.get('Jug') if ent.get('Jug', 0) else 0.0
    ratioVent = ((ent.get('Pfav', 0) - ent.get('Pcon', 0)) / ent.get('Jug')) if ent.get('Jug', 0) else 0.0

    result = (ratioV, ent.get('V', 0), ratioVent, ent.get('Pfav', 0))

    return result


def ordenEstadsLiga(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True) -> int:
    if abr not in estads:
        valCorrectos = ", ".join(sorted(estads.keys()))
        raise KeyError(f"ordenEstadsLiga: equipo (abr) '{abr}' desconocido. Equipos validos: {valCorrectos}")
    targEquipo = estads[abr]
    if eq not in targEquipo:
        valCorrectos = ", ".join(sorted(targEquipo.keys()))
        raise KeyError(f"ordenEstadsLiga: ref (eq) '{eq}' desconocido. Referencias válidas: {valCorrectos}")
    targValores = targEquipo[eq]
    if clave not in targValores:
        valCorrectos = ", ".join(sorted(targValores.keys()))
        raise KeyError(f"ordenEstadsLiga: clave '{clave}' desconocida. Claves válidas: {valCorrectos}")

    auxRef = targValores[clave][subclave] if isinstance(targValores[clave], tuple) else targValores[clave]

    valAcomp = [estads[e][eq][clave] for e in estads.keys()]

    keyGetter = (lambda v, subclave: v[subclave]) if isinstance(targValores[clave], tuple) else (lambda v, subclave: v)

    comparaValores = (lambda x, auxref: x > auxref) if decrec else (lambda x, auxref: x < auxref)

    return sum([comparaValores(keyGetter(v, subclave), auxRef) for v in valAcomp]) + 1


def extraeCampoYorden(estads: pd.DataFrame, estadsOrden: pd.DataFrame, eq: str = 'eq', clave: str = 'P',
                      estadistico='mean'):
    targetCol = (eq, clave, estadistico)

    if targetCol not in estads.index:
        valCorrectos = ", ".join(sorted(estads.index).map(str))
        raise KeyError(
            f"extraeCampoYorden: parametros para dato '{targetCol}' desconocidos. Referencias válidas: {valCorrectos}")

    valor = estads.loc[targetCol]
    orden = estadsOrden.loc[targetCol]

    return valor, orden


def precalculaOrdenEstadsLiga(dfEstads: pd.DataFrame, listAscending=None):
    resultDict = dict()

    colsChangeMult = set(listAscending) if listAscending else {}

    for col in dfEstads.columns:
        multiplicador = 1 if col in colsChangeMult else -1  # En general queremos que sea descendente
        colAusar = multiplicador * dfEstads[col]
        ordenIDX = colAusar.index[colAusar.argsort()]
        auxDict = {eq: pos for pos, eq in enumerate(ordenIDX, start=1)}
        auxSerie = pd.Series(data=auxDict)
        resultDict[col] = auxSerie

    result = pd.DataFrame.from_dict(resultDict, orient='columns').sort_index()
    return result


def auxCalculaEstadsSubDataframe(dfEntrada: pd.DataFrame):
    FILASESTADISTICOS = ['count', 'mean', 'std', 'min', '50%', 'max']
    ROWRENAMER = {'50%': 'median'}

    estadisticosNumber = dfEntrada.describe(include=[np.number], percentiles=[.50])
    # Necesario porque describe trata los bool como categóricos
    estadisticosBool = dfEntrada.select_dtypes([np.bool_]).astype(np.int64).apply(
        lambda c: c.describe(percentiles=[.50]))

    auxEstadisticos = pd.concat([estadisticosNumber, estadisticosBool], axis=1).T[FILASESTADISTICOS].T

    # Hay determinados campos que no tiene sentido sumar. Así que sumamos todos y luego ponemos a nan los que no
    # Para estos tengo dudas filosóficas de cómo calcular la media (¿media del valor de cada partido o calcular el
    # ratio a partir de las sumas?
    sumas = dfEntrada[auxEstadisticos.columns].select_dtypes([np.number, np.bool_]).sum()

    sumasDF = pd.DataFrame(sumas).T
    sumasDF.index = pd.Index(['sum'])

    finalDF = pd.concat([auxEstadisticos, sumasDF]).rename(index=ROWRENAMER)

    result = finalDF.unstack()

    return result


def auxEtiqPartido(tempData: TemporadaACB, rivalAbr, esLocal=None, locEq=None, usaAbr=False, usaLargo=False):
    if (esLocal is None) and (locEq is None):
        raise ValueError("auxEtiqPartido: debe aportar o esLocal o locEq")

    auxLoc = esLocal if (esLocal is not None) else (locEq in LOCALNAMES)
    prefLoc = "vs " if auxLoc else "@"

    ordenNombre = -1 if usaLargo else 0

    nombre = rivalAbr if usaAbr else sorted(tempData.Calendario.tradEquipos['c2n'][rivalAbr], key=lambda n: len(n))[
        ordenNombre]

    result = f"{prefLoc}{nombre}"

    return result


def equipo2clasif(clasifLiga, abrEq):
    result = None

    for eqData in clasifLiga:
        if abrEq in eqData['abrevsEq']:
            return eqData

    return result


def ordenEstadsLiga(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True) -> int:
    if abr not in estads:
        valCorrectos = ", ".join(sorted(estads.keys()))
        raise KeyError(f"ordenEstadsLiga: equipo (abr) '{abr}' desconocido. Equipos validos: {valCorrectos}")
    targEquipo = estads[abr]
    if eq not in targEquipo:
        valCorrectos = ", ".join(sorted(targEquipo.keys()))
        raise KeyError(f"ordenEstadsLiga: ref (eq) '{eq}' desconocido. Referencias válidas: {valCorrectos}")
    targValores = targEquipo[eq]
    if clave not in targValores:
        valCorrectos = ", ".join(sorted(targValores.keys()))
        raise KeyError(f"ordenEstadsLiga: clave '{clave}' desconocida. Claves válidas: {valCorrectos}")

    auxRef = targValores[clave][subclave] if isinstance(targValores[clave], tuple) else targValores[clave]

    valAcomp = [estads[e][eq][clave] for e in estads.keys()]

    keyGetter = (lambda v, subclave: v[subclave]) if isinstance(targValores[clave], tuple) else (lambda v, subclave: v)

    comparaValores = (lambda x, auxref: x > auxref) if decrec else (lambda x, auxref: x < auxref)

    return sum([comparaValores(keyGetter(v, subclave), auxRef) for v in valAcomp]) + 1


def extraeCampoYorden(estads: pd.DataFrame, estadsOrden: pd.DataFrame, eq: str = 'eq', clave: str = 'P',
                      estadistico='mean'):
    targetCol = (eq, clave, estadistico)

    if targetCol not in estads.index:
        valCorrectos = ", ".join(sorted(estads.index).map(str))
        raise KeyError(
            f"extraeCampoYorden: parametros para dato '{targetCol}' desconocidos. Referencias válidas: {valCorrectos}")

    valor = estads.loc[targetCol]
    orden = estadsOrden.loc[targetCol]

    return valor, orden


def precalculaOrdenEstadsLiga(dfEstads: pd.DataFrame, listAscending=None):
    resultDict = dict()

    colsChangeMult = set(listAscending) if listAscending else {}

    for col in dfEstads.columns:
        multiplicador = 1 if col in colsChangeMult else -1  # En general queremos que sea descendente
        colAusar = multiplicador * dfEstads[col]
        ordenIDX = colAusar.index[colAusar.argsort()]
        auxDict = {eq: pos for pos, eq in enumerate(ordenIDX, start=1)}
        auxSerie = pd.Series(data=auxDict)
        resultDict[col] = auxSerie

    result = pd.DataFrame.from_dict(resultDict, orient='columns').sort_index()
    return result


def auxCalculaEstadsSubDataframe(dfEntrada: pd.DataFrame):
    FILASESTADISTICOS = ['count', 'mean', 'std', 'min', '50%', 'max']
    ROWRENAMER = {'50%': 'median'}

    estadisticosNumber = dfEntrada.describe(include=[np.number], percentiles=[.50])
    # Necesario porque describe trata los bool como categóricos
    estadisticosBool = dfEntrada.select_dtypes([np.bool_]).astype(np.int64).apply(
        lambda c: c.describe(percentiles=[.50]))

    auxEstadisticos = pd.concat([estadisticosNumber, estadisticosBool], axis=1).T[FILASESTADISTICOS].T

    # Hay determinados campos que no tiene sentido sumar. Así que sumamos todos y luego ponemos a nan los que no
    # Para estos tengo dudas filosóficas de cómo calcular la media (¿media del valor de cada partido o calcular el
    # ratio a partir de las sumas?
    sumas = dfEntrada[auxEstadisticos.columns].select_dtypes([np.number, np.bool_]).sum()

    sumasDF = pd.DataFrame(sumas).T
    sumasDF.index = pd.Index(['sum'])

    finalDF = pd.concat([auxEstadisticos, sumasDF]).rename(index=ROWRENAMER)

    result = finalDF.unstack()

    return result


def auxEtiqPartido(tempData: TemporadaACB, rivalAbr, esLocal=None, locEq=None, usaAbr=False, usaLargo=False):
    if (esLocal is None) and (locEq is None):
        raise ValueError("auxEtiqPartido: debe aportar o esLocal o locEq")

    auxLoc = esLocal if (esLocal is not None) else (locEq in LOCALNAMES)
    prefLoc = "vs " if auxLoc else "@"

    ordenNombre = -1 if usaLargo else 0

    nombre = rivalAbr if usaAbr else sorted(tempData.Calendario.tradEquipos['c2n'][rivalAbr], key=lambda n: len(n))[
        ordenNombre]

    result = f"{prefLoc}{nombre}"

    return result


def equipo2clasif(clasifLiga, abrEq):
    result = None

    for eqData in clasifLiga:
        if abrEq in eqData['abrevsEq']:
            return eqData

    return result


def ordenEstadsLiga(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True) -> int:
    if abr not in estads:
        valCorrectos = ", ".join(sorted(estads.keys()))
        raise KeyError(f"ordenEstadsLiga: equipo (abr) '{abr}' desconocido. Equipos validos: {valCorrectos}")
    targEquipo = estads[abr]
    if eq not in targEquipo:
        valCorrectos = ", ".join(sorted(targEquipo.keys()))
        raise KeyError(f"ordenEstadsLiga: ref (eq) '{eq}' desconocido. Referencias válidas: {valCorrectos}")
    targValores = targEquipo[eq]
    if clave not in targValores:
        valCorrectos = ", ".join(sorted(targValores.keys()))
        raise KeyError(f"ordenEstadsLiga: clave '{clave}' desconocida. Claves válidas: {valCorrectos}")

    auxRef = targValores[clave][subclave] if isinstance(targValores[clave], tuple) else targValores[clave]

    valAcomp = [estads[e][eq][clave] for e in estads.keys()]

    keyGetter = (lambda v, subclave: v[subclave]) if isinstance(targValores[clave], tuple) else (lambda v, subclave: v)

    comparaValores = (lambda x, auxref: x > auxref) if decrec else (lambda x, auxref: x < auxref)

    return sum([comparaValores(keyGetter(v, subclave), auxRef) for v in valAcomp]) + 1


def extraeCampoYorden(estads: pd.DataFrame, estadsOrden: pd.DataFrame, eq: str = 'eq', clave: str = 'P',
                      estadistico='mean'):
    targetCol = (eq, clave, estadistico)

    if targetCol not in estads.index:
        valCorrectos = ", ".join(sorted(estads.index).map(str))
        raise KeyError(
            f"extraeCampoYorden: parametros para dato '{targetCol}' desconocidos. Referencias válidas: {valCorrectos}")

    valor = estads.loc[targetCol]
    orden = estadsOrden.loc[targetCol]

    return valor, orden


def precalculaOrdenEstadsLiga(dfEstads: pd.DataFrame, listAscending=None):
    resultDict = dict()

    colsChangeMult = set(listAscending) if listAscending else {}

    for col in dfEstads.columns:
        multiplicador = 1 if col in colsChangeMult else -1  # En general queremos que sea descendente

        colWrk = dfEstads[col]
        if (colWrk.isna().any()):
            if (col in DEFAULTNAVALUES):
                colWrk.fillna(value=DEFAULTNAVALUES[col], inplace=True)
            else:
                print(f"SMACB.TemporadaACB.precalculaOrdenEstadsLiga: Column {col} has NAs unhandled!")
                print(colWrk)

        colAusar = multiplicador * colWrk
        ordenIDX = colAusar.index[colAusar.argsort()]
        auxDict = {eq: pos for pos, eq in enumerate(ordenIDX, start=1)}
        auxSerie = pd.Series(data=auxDict)
        resultDict[col] = auxSerie

    result = pd.DataFrame.from_dict(resultDict, orient='columns').sort_index()
    return result


def ordenEstadsLiga(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True) -> int:
    if abr not in estads:
        valCorrectos = ", ".join(sorted(estads.keys()))
        raise KeyError(f"ordenEstadsLiga: equipo (abr) '{abr}' desconocido. Equipos validos: {valCorrectos}")
    targEquipo = estads[abr]
    if eq not in targEquipo:
        valCorrectos = ", ".join(sorted(targEquipo.keys()))
        raise KeyError(f"ordenEstadsLiga: ref (eq) '{eq}' desconocido. Referencias válidas: {valCorrectos}")
    targValores = targEquipo[eq]
    if clave not in targValores:
        valCorrectos = ", ".join(sorted(targValores.keys()))
        raise KeyError(f"ordenEstadsLiga: clave '{clave}' desconocida. Claves válidas: {valCorrectos}")

    auxRef = targValores[clave][subclave] if isinstance(targValores[clave], tuple) else targValores[clave]

    valAcomp = [estads[e][eq][clave] for e in estads.keys()]

    keyGetter = (lambda v, subclave: v[subclave]) if isinstance(targValores[clave], tuple) else (lambda v, subclave: v)

    comparaValores = (lambda x, auxref: x > auxref) if decrec else (lambda x, auxref: x < auxref)

    return sum([comparaValores(keyGetter(v, subclave), auxRef) for v in valAcomp]) + 1


def extraeCampoYorden_XXX(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True):
    if abr not in estads:
        valCorrectos = ", ".join(sorted(estads.keys()))
        raise KeyError(f"ordenEstadsLiga: equipo (abr) '{abr}' desconocido. Equipos validos: {valCorrectos}")
    targEquipo = estads[abr]
    if eq not in targEquipo:
        valCorrectos = ", ".join(sorted(targEquipo.keys()))
        raise KeyError(f"ordenEstadsLiga: ref (eq) '{eq}' desconocido. Referencias válidas: {valCorrectos}")
    targValores = targEquipo[eq]
    if clave not in targValores:
        valCorrectos = ", ".join(sorted(targValores.keys()))
        raise KeyError(f"ordenEstadsLiga: clave '{clave}' desconocida. Claves válidas: {valCorrectos}")

    valor = targValores[clave][subclave] if isinstance(targValores[clave], tuple) else targValores[clave]
    orden = ordenEstadsLiga(estads, abr, eq, clave, subclave, decrec)

    return valor, orden

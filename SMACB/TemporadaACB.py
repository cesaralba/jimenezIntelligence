'''
Created on Jan 4, 2018

@author: calba
'''

from argparse import Namespace
from collections import defaultdict
from copy import copy
from pickle import dump, load
from statistics import mean, median, stdev
from traceback import print_exception
from typing import Iterable

import numpy as np
import pandas as pd
from itertools import product
from sys import exc_info, setrecursionlimit
from time import gmtime

from Utils.FechaHora import fechaParametro2pddatetime
from Utils.Pandas import combinaPDindexes
from Utils.Web import creaBrowser
from .CalendarioACB import calendario_URLBASE, CalendarioACB, URL_BASE
from .Constants import OtherLoc, EqRival, OtherTeam
from .FichaJugador import FichaJugador
from .PartidoACB import PartidoACB

COLSESTADSASCENDING = [
    ('Info', 'prorrogas', 'mean'),
    ('Info', 'prorrogas', 'sum'),
    ('Eq', 'BP', 'mean'),
    ('Eq', 'BP', 'min'),
    ('Eq', 'BP', '50%'),
    ('Eq', 'BP', 'max'),
    ('Eq', 'BP', 'sum'),
    ('Eq', 'TAP-C', 'mean'),
    ('Eq', 'TAP-C', 'min'),
    ('Eq', 'TAP-C', '50%'),
    ('Eq', 'TAP-C', 'max'),
    ('Eq', 'TAP-C', 'sum'),
    ('Eq', 'FP-C', 'mean'),
    ('Eq', 'FP-C', 'min'),
    ('Eq', 'FP-C', '50%'),
    ('Eq', 'FP-C', 'max'),
    ('Eq', 'FP-C', 'sum'),
    ('Rival', 'P', 'mean'),
    ('Rival', 'P', 'std'),
    ('Rival', 'P', 'min'),
    ('Rival', 'P', '50%'),
    ('Rival', 'P', 'max'),
    ('Rival', 'P', 'sum'),
    ('Rival', 'OER', 'mean'),
    ('Rival', 'OER', 'min'),
    ('Rival', 'OER', '50%'),
    ('Rival', 'OER', 'max'),
    ('Rival', 'OER', 'sum'),
    ('Rival', 'OERpot', 'mean'),
    ('Rival', 'OERpot', 'min'),
    ('Rival', 'OERpot', '50%'),
    ('Rival', 'OERpot', 'max'),
    ('Rival', 'OERpot', 'sum'),
]


class TemporadaACB(object):
    '''
    Aglutina calendario y lista de partidos
    '''

    def __init__(self, **kwargs):
        self.competicion = kwargs.get('competicion', "LACB")
        self.edicion = kwargs.get('edicion', None)
        self.urlbase = kwargs.get('urlbase', calendario_URLBASE)
        descargaFichas = kwargs.get('descargaFichas', False)

        self.timestamp = gmtime()
        self.Calendario = CalendarioACB(competicion=self.competicion, edicion=self.edicion, urlbase=self.urlbase)
        self.Partidos = dict()
        self.changed = False
        self.tradJugadores = {'id2nombres': defaultdict(set), 'nombre2ids': defaultdict(set)}
        self.descargaFichas = descargaFichas
        self.fichaJugadores = dict()
        self.fichaEntrenadores = dict()

    def actualizaTemporada(self, home=None, browser=None, config=Namespace()):

        if isinstance(config, dict):
            config = Namespace(**config)

        if browser is None:
            browser = creaBrowser(config)
            browser.open(URL_BASE)

        self.Calendario.actualizaCalendario(browser=browser, config=config)

        if 'procesabio' in config and config.procesaBio:
            self.descargaFichas = True

        partidosBajados = set()

        for partido in self.Calendario.Partidos:
            if partido in self.Partidos:
                continue

            try:
                nuevoPartido = PartidoACB(**(self.Calendario.Partidos[partido]))
                nuevoPartido.descargaPartido(home=home, browser=browser, config=config)
                self.Partidos[partido] = nuevoPartido
                self.actualizaNombresEquipo(nuevoPartido)
                partidosBajados.add(partido)

                if self.descargaFichas:
                    self.actualizaFichasPartido(nuevoPartido, browser=browser, config=config)
                self.actualizaTraduccionesJugador(nuevoPartido)

            except KeyboardInterrupt:
                print("actualizaTemporada: Ejecución terminada por el usuario")
                break
            except BaseException:
                print("actualizaTemporada: problemas descargando  partido '%s': %s" % (partido, exc_info()))
                print_exception(*exc_info())

            if 'justone' in config and config.justone:  # Just downloads a game (for testing/dev purposes)
                break

        if partidosBajados:
            self.changed = True
            self.timestamp = gmtime()

        return partidosBajados

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

    def extraeDataframeJugadores(self):

        def jorFech2periodo(dfTemp):
            periodoAct = 0
            jornada = dict()
            claveMin = dict()
            claveMax = dict()
            curVal = None
            jf2periodo = defaultdict(lambda: defaultdict(int))

            dfPairs = dfTemp.apply(lambda r: (r['Fecha'].date(), r['jornada']), axis=1).unique()
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

        dfPartidos = [partido.jugadoresAdataframe() for partido in self.Partidos.values()]
        dfResult = pd.concat(dfPartidos, axis=0, ignore_index=True, sort=True)

        periodos = jorFech2periodo(dfResult)

        dfResult['periodo'] = dfResult.apply(lambda r: periodos[r['jornada']][r['Fecha'].date()], axis=1)

        return (dfResult)

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

        peOrd = sorted([p for p in peCal], key=lambda x: x['fecha'])
        juOrdTem = sorted([self.Partidos[p['url']] for p in juCal], key=lambda x: x.fechaPartido)

        sigPart = peOrd.pop(0)
        abrevsEq = self.Calendario.abrevsEquipo(abrEq)
        abrRival = sigPart['participantes'].difference(abrevsEq).pop()
        juRivCal, peRivCal = self.Calendario.partidosEquipo(abrRival)
        peRivOrd = sorted([p for p in peRivCal if p['jornada'] != sigPart['jornada']], key=lambda x: x['fecha'])
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
        result['CasaFuera'] = {'Local': defaultdict(int), 'Visitante': defaultdict(int)}

        partidosAcontar = [p for p in juCal if self.Partidos[p['url']].fechaPartido < fecha] if fecha else juCal

        for datosCal in partidosAcontar:
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

    def precalcEstadsEquipo(self, abrEq=None, fecha=None):

        auxEstads = defaultdict(lambda: defaultdict(list))

        if abrEq:
            juCal, _ = self.Calendario.partidosEquipo(abrEq)
            listaPartidos = juCal
            partidosAcontar = [p for p in listaPartidos if
                               self.Partidos[p['url']].fechaPartido < fecha] if fecha else listaPartidos
        else:
            listaPartidos = []
            for auxAbr in self.Calendario.tradEquipos['i2c'].values():
                ab = list(auxAbr)[0]
                juCal, _ = self.Calendario.partidosEquipo(ab)
                listaPartidos.extend(list(product([ab], juCal)))
            partidosAcontar = [p for p in listaPartidos if
                               self.Partidos[p[1]['url']].fechaPartido < fecha] if fecha else listaPartidos

        for datosCal in partidosAcontar:
            if abrEq:
                abrevsEq = self.Calendario.abrevsEquipo(abrEq)
                partCal = datosCal
                abrevUsada = abrevsEq.intersection(datosCal['participantes']).pop()
            else:
                ab, partCal = datosCal
                abrevsEq = self.Calendario.abrevsEquipo(ab)
                abrevUsada = abrevsEq.intersection(partCal['participantes']).pop()

            locEq = partCal['abrev2loc'][abrevUsada]
            locRival = OtherLoc(locEq)
            # datosEq = datosCal['equipos'][locEq]
            datosRival = partCal['equipos'][locRival]
            abrevRival = datosRival['abrev']

            datosPartido = self.Partidos[partCal['url']]
            estads = datosPartido.estadsPartido()
            estadsEq = estads[locEq]
            estadsEq['fecha'] = partCal['fecha']
            estadsRival = estads[locRival]
            estadsRival['fecha'] = partCal['fecha']

            for k, v in estadsEq.items():
                auxEstads['eq'][k].append(v)
            for k, v in estadsRival.items():
                auxEstads['rival'][k].append(v)

        return auxEstads

    def estadsEquipo(self, abrEq=None, fecha=None):

        result = defaultdict(dict)

        auxEstads = self.precalcEstadsEquipo(abrEq, fecha)

        for k in ['POS', 'POStot', 'Segs', 'P', 'Priv', 'Ptot', 'OER', 'OERpot', 'T1-C', 'T1-I', 'T2-C', 'T2-I', 'T3-C',
                  'T3-I', 'TC-C', 'TC-I', 'T1%', 'T2%', 'T3%', 'TC%', 't2/tc-I',
                  't3/tc-I', 't2/tc-C', 't3/tc-C', 'eff-t2', 'eff-t3', 'ppTC', 'R-D', 'R-O', 'REB-T', 'RO/TC-F',
                  'EffRebD',
                  'EffRebO', 'A', 'BP', 'BR', 'A/BP', 'A/TC-C', 'FP-F', 'TAP-F']:
            for l in ['eq', 'rival']:
                result[l][k] = (
                    mean(auxEstads[l][k]), median(auxEstads[l][k]), stdev(auxEstads[l][k]), max(auxEstads[l][k]),
                    min(auxEstads[l][k]))

        for k in '123C':
            kI = f'T{k}-I'
            kC = f'T{k}-C'
            kRes = f'T{k}%-calc'
            for l in ['eq', 'rival']:
                result[l][kRes] = sum(auxEstads[l][kC]) / sum(auxEstads[l][kI]) * 100.0

        for l in ['eq', 'rival']:
            result[l]['Parts'] = len(auxEstads[l]['P'])
            result[l]['t2/tc-I-calc'] = sum(auxEstads[l]['T2-I']) / sum(auxEstads[l]['TC-I'])
            result[l]['t3/tc-I-calc'] = sum(auxEstads[l]['T3-I']) / sum(auxEstads[l]['TC-I'])
            result[l]['t2/tc-C-calc'] = sum(auxEstads[l]['T2-C']) / sum(auxEstads[l]['TC-C'])
            result[l]['t3/tc-C-calc'] = sum(auxEstads[l]['T3-C']) / sum(auxEstads[l]['TC-C'])
            result[l]['eff-t2-calc'] = sum(auxEstads[l]['T2-C']) * 2 / (
                    sum(auxEstads[l]['T2-C']) * 2 + sum(auxEstads[l]['T3-C']) * 3)
            result[l]['eff-t3-calc'] = sum(auxEstads[l]['T3-C']) * 3 / (
                    sum(auxEstads[l]['T2-C']) * 2 + sum(auxEstads[l]['T3-C']) * 3)
            result[l]['A/TC-C-calc'] = sum(auxEstads[l]['A']) / sum(auxEstads[l]['TC-C']) * 100.0
            result[l]['A/BP-calc'] = sum(auxEstads[l]['A']) / sum(auxEstads[l]['BP'])
            result[l]['RO/TC-F-calc'] = sum(auxEstads[l]['R-O']) / (
                    sum(auxEstads[l]['TC-I']) - sum(auxEstads[l]['TC-C']))

        return result

    def estadsLiga(self, fecha=None):
        result = dict()

        for auxAbr in self.Calendario.tradEquipos['i2c'].values():
            ab = list(auxAbr)[0]
            result[ab] = self.estadsEquipo(ab, fecha)

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
            auxDF[col] = auxDF[col]

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

    def dfPartidosLV2ER(self, partidos: pd.DataFrame, abrEq: str):
        COLSINFO = ['Jornada', 'fechaPartido', 'Pabellon', 'Asistencia', 'prorrogas', 'url', 'competicion', 'temporada',
                    'idPartido', 'Ptot', 'POStot']

        idEq = list(self.Calendario.tradEquipos['c2i'][abrEq])[0]
        partidosEq = partidos.loc[(partidos['Local', 'id'] == idEq) | (partidos['Visitante', 'id'] == idEq)]

        finalDFlist = []
        for esLocal in [True, False]:
            tagEq, tagRival = ('Local', 'Visitante') if esLocal else ('Visitante', 'Local')

            auxDFlocal = partidosEq.loc[(partidosEq['Local', 'id'] == idEq) == esLocal]
            infoDF = auxDFlocal['Info'][COLSINFO]
            eqDF = auxDFlocal[tagEq]
            rivalDF = auxDFlocal[tagRival]

            auxDF = pd.concat([infoDF, eqDF, rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
            finalDFlist.append(auxDF)

        result = pd.concat(finalDFlist)

        return result.sort_values(by=('Info', 'fechaPartido'))

    def dfEstadsEquipo(self, dfEstadsPartidosEq: pd.DataFrame, abrEq: str):
        FILASESTADISTICOS = ['count', 'mean', 'std', 'min', '50%', 'max']
        COLRENAMER = {'50%': 'median'}
        COLDROPPER = [('Info', 'Jornada')]

        abrevsEq = self.Calendario.abrevsEquipo(abrEq)

        estadPartidos = dfEstadsPartidosEq.loc[dfEstadsPartidosEq[('Eq', 'abrev')].isin(abrevsEq)]

        estadisticosNumber = estadPartidos.describe(include=[np.number], percentiles=[.50])
        # Necesario porque describe trata los bool como categóricos
        estadisticosBool = estadPartidos.select_dtypes([np.bool]).astype(np.int64).apply(
            lambda c: c.describe(percentiles=[.50]))

        auxEstadisticos = pd.concat([estadisticosNumber, estadisticosBool], axis=1).T[FILASESTADISTICOS].T
        auxEstadisticos[('Info', 'prorrogas')] = estadPartidos.loc[estadPartidos[('Info', 'prorrogas')] != 0][
            ('Info', 'prorrogas')].describe()

        # Hay determinados campos que no tiene sentido sumar. Así que sumamos todos y luego ponemos a nan los que no
        # Para estos tengo dudas filosóficas de cómo calcular la media (¿media del valor de cada partido o calcular el
        # ratio a partir de las sumas?
        sumas = estadPartidos[auxEstadisticos.columns].select_dtypes([np.number, np.bool]).sum()

        # Elimina valores que no tienen sentido y que no se van a recalculoar más tarde
        for eq in EqRival:
            for col in [(eq, 'convocados'), (eq, 'utilizados')]:
                sumas[col] = np.nan
        sumas[('Info', 'Jornada')] = np.nan

        sumasDF = pd.DataFrame(sumas).T
        sumasDF.index = pd.Index(['sum'])

        finalDF = pd.concat([auxEstadisticos, sumasDF]).drop(columns=COLDROPPER).rename(columns=COLRENAMER)

        # Calculate sum field for ratios as the ratio of sum fields. Shooting percentages
        for k in '123C':
            kI = f'T{k}-I'
            kC = f'T{k}-C'
            kRes = f'T{k}%'
            for eq in EqRival:
                finalDF[(eq, kRes)]['sum'] = finalDF[(eq, kC)]['sum'] / finalDF[(eq, kI)]['sum'] * 100.0

        # Calculate sum field for ratios as the ratio of sum fields. Other ratios
        for eq in EqRival:
            for k in '23':
                finalDF[(eq, f't{k}/tc-I')]['sum'] = finalDF[(eq, f'T{k}-I')]['sum'] / finalDF[(eq, 'TC-I')][
                    'sum'] * 100.0
                finalDF[(eq, f't{k}/tc-C')]['sum'] = finalDF[(eq, f'T{k}-C')]['sum'] / finalDF[(eq, 'TC-C')][
                    'sum'] * 100.0
                finalDF[(eq, f'eff-t{k}')]['sum'] = finalDF[(eq, f'T{k}-C')]['sum'] * int(k) / (
                        finalDF[(eq, 'T2-C')]['sum'] * 2 + finalDF[(eq, 'T3-C')]['sum'] * 3) * 100.0
            finalDF[(eq, 'A/TC-C')]['sum'] = finalDF[(eq, 'A')]['sum'] / finalDF[(eq, 'TC-C')]['sum'] * 100.0
            finalDF[(eq, 'A/BP')]['sum'] = finalDF[(eq, 'A')]['sum'] / finalDF[(eq, 'BP')]['sum']
            finalDF[(eq, 'RO/TC-F')]['sum'] = finalDF[(eq, 'R-O')]['sum'] / (
                    finalDF[(eq, 'TC-I')]['sum'] - finalDF[(eq, 'TC-C')]['sum']) * 100.0
            finalDF[(eq, 'ppTC')]['sum'] = (finalDF[(eq, 'T2-C')]['sum'] * 2 + finalDF[(eq, 'T3-C')]['sum'] * 3) / (
                    finalDF[(eq, 'T2-I')]['sum'] + finalDF[(eq, 'T3-I')]['sum'])
            finalDF[(eq, 'OER')]['sum'] = finalDF[(eq, 'P')]['sum'] / finalDF[(eq, 'POS')]['sum']
            finalDF[(eq, 'OERpot')]['sum'] = finalDF[(eq, 'P')]['sum'] / (
                    finalDF[(eq, 'POS')]['sum'] - finalDF[(eq, 'BP')]['sum'])
            finalDF[(eq, 'EffRebD')]['sum'] = finalDF[(eq, 'R-D')]['sum'] / (
                    finalDF[(eq, 'R-D')]['sum'] + finalDF[(OtherTeam(eq), 'R-O')]['sum'])
            finalDF[(eq, 'EffRebO')]['sum'] = finalDF[(eq, 'R-O')]['sum'] / (
                    finalDF[(eq, 'R-O')]['sum'] + finalDF[(OtherTeam(eq), 'R-D')]['sum'])

        result = finalDF.unstack()
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

        result = pd.DataFrame.from_dict(data=resultDict, orient='index')

        return result


def calculaTempStats(datos, clave, filtroFechas=None):
    if clave not in datos:
        raise (KeyError, "Clave '%s' no está en datos." % clave)

    if filtroFechas:
        datosWrk = datos
    else:
        datosWrk = datos

    agg = datosWrk.set_index('codigo')[clave].astype('float64').groupby('codigo').agg(['mean', 'std', 'count',
                                                                                       'median', 'min', 'max',
                                                                                       'skew'])
    agg1 = agg.rename(columns=dict([(x, clave + "-" + x) for x in agg.columns])).reset_index()
    return agg1


def calculaZ(datos, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    finalKeys = ['codigo', 'competicion', 'temporada', 'jornada', 'CODequipo', 'CODrival', 'esLocal',
                 'haJugado', 'Fecha', 'periodo', clave]
    finalTypes = {'CODrival': 'category', 'esLocal': 'bool', 'CODequipo': 'category',
                  ('half-' + clave): 'bool', ('aboveAvg-' + clave): 'bool', (clZ + '-' + clave): 'float64'}
    # We already merged SuperManager?
    if 'pos' in datos.columns:
        finalKeys.append('pos')
        finalTypes['pos'] = 'category'

    if filtroFechas:
        datosWrk = datos  # TODO: filtro de fechas
    else:
        datosWrk = datos

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


def extraeCampoYorden(estads: dict, abr: str, eq: str = 'eq', clave: str = 'P', subclave=0, decrec: bool = True):
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

    result = pd.DataFrame.from_dict(resultDict, orient='columns')
    return result

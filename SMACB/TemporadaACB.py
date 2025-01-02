"""
Created on Jan 4, 2018

@author: calba
"""

import logging
import sys
import traceback
from collections import defaultdict
from copy import copy
from decimal import Decimal
from itertools import chain
from operator import itemgetter
from pickle import dump, load
from sys import exc_info, setrecursionlimit
from time import gmtime, strftime
from traceback import print_exception
from typing import Any, Iterable, Dict, Tuple, List
from typing import Optional

import numpy as np
import pandas as pd
from CAPcore.Misc import onlySetElement
from CAPcore.Web import mergeURL

from Utils.FechaHora import fechaParametro2pddatetime
from Utils.Pandas import combinaPDindexes
from Utils.Web import prepareDownloading
from .CalendarioACB import calendario_URLBASE, CalendarioACB, URL_BASE
from .Constants import (EqRival, filaMergeTrayectoria, filaTrayectoriaEq, infoClasifBase, infoClasifEquipo,
                        infoEqCalendario, infoPartLV, infoSigPartido, LOCALNAMES, LocalVisitante, OtherLoc, OtherTeam,
                        infoClasifComplMasD2, infoClasifComplPareja, )
from .FichaJugador import FichaJugador, CAMBIOSJUGADORES
from .PartidoACB import PartidoACB
from .PlantillaACB import descargaPlantillasCabecera, PlantillaACB, CAMBIOSCLUB, CambiosPlantillaTipo

logger = logging.getLogger()

DEFAULTNAVALUES = {('Eq', 'convocados', 'sum'): 0, ('Eq', 'utilizados', 'sum'): 0, ('Info', 'prorrogas', 'count'): 0,
                   ('Info', 'prorrogas', 'max'): 0, ('Info', 'prorrogas', 'mean'): 0,
                   ('Info', 'prorrogas', 'median'): 0, ('Info', 'prorrogas', 'min'): 0, ('Info', 'prorrogas', 'std'): 0,
                   ('Info', 'prorrogas', 'sum'): 0, ('Rival', 'convocados', 'sum'): 0,
                   ('Rival', 'utilizados', 'sum'): 0, }

JUGADORESDESCARGADOS = set()
AUXCAMBIOS = CAMBIOSJUGADORES  # For the sake of formatter


def auxJorFech2periodo(dfTemp: pd.DataFrame):
    periodoAct: int = 0
    jornada = {}
    claveMin = {}
    claveMax = {}
    curVal: Optional[Tuple[Any, str]] = None
    jf2periodo = defaultdict(lambda: defaultdict(int))

    dfPairs: List[Tuple[Any, str]] = dfTemp.apply(lambda r: (r['fechaPartido'].date(), r['jornada']), axis=1).unique()
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

    p2k = {jId: f"{claveMin[jId]}" + (
        f"\na {claveMax[jId]}" if (claveMin[jId] != claveMax[jId]) else "") + f"\n(J:{jData:2})" for jId, jData in
           jornada.items()}

    result = {}
    for j in jf2periodo:
        result[j] = {}
        for d in jf2periodo[j]:
            result[j][d] = p2k[jf2periodo[j][d]]

    return result


class TemporadaACB:
    """
    Aglutina calendario y lista de partidos
    """

    # TODO: función __str__

    def __init__(self, **kwargs):
        """

        :param kwargs:
        * competicion: Defecto "LACB")
        * edicion Defecto: None
        * descargaFichas Defecto= False
        * descargaPlantillas Defecto= False)

        """
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
        self.fichaJugadores: Dict[str, FichaJugador] = dict()
        self.fichaEntrenadores = dict()
        self.plantillas: Dict[str, PlantillaACB] = {}

    def __repr__(self):
        tstampStr = strftime("%Y%m%d-%H:%M:%S", self.timestamp)
        result = f"{self.competicion} Temporada: {self.edicion} Datos: {tstampStr}"
        return result

    def actualizaTemporada(self, home=None, browser=None, config=None):
        changeOrig = self.changed

        browser, config = prepareDownloading(browser, config, URL_BASE)

        self.Calendario.actualizaCalendario(browser=browser, config=config)
        self.Calendario.actualizaDatosPlayoffJornada()  # Para compatibilidad hacia atrás

        partidosBajados = set()

        for partido in sorted(set(self.Calendario.Partidos.keys()).difference(set(self.Partidos.keys()))):
            try:
                nuevoPartido = PartidoACB(**(self.Calendario.Partidos[partido]))
                nuevoPartido.descargaPartido(home=home, browser=browser, config=config)
                if nuevoPartido.check():
                    self.Partidos[partido] = nuevoPartido
                    partidosBajados.add(partido)
                    self.actualizaInfoAuxiliar(nuevoPartido, browser, config)
            except KeyboardInterrupt:
                print("actualizaTemporada: Ejecución terminada por el usuario")
                break
            except BaseException:
                print(f"actualizaTemporada: problemas descargando  partido '{partido}': {exc_info()}")
                print_exception(*exc_info())

            if 'justone' in config and config.justone:  # Just downloads a game (for testing/dev purposes)
                break

        self.changed |= (len(partidosBajados) > 0)

        if self.descargaPlantillas:
            resPlant = self.actualizaPlantillas(browser=browser, config=config)
            self.changed |= resPlant
            if resPlant:
                self.changed |= self.actualizaFichaJugadoresFromCambiosPlant(CAMBIOSCLUB)

        if self.changed != changeOrig:
            self.timestamp = gmtime()

        return partidosBajados

    def actualizaInfoAuxiliar(self, nuevoPartido, browser, config):
        self.actualizaNombresEquipo(nuevoPartido)
        self.actualizaFichasPartido(nuevoPartido, browser=browser, config=config)
        self.actualizaTraduccionesJugador(nuevoPartido)
        # Añade la información de equipos de partido a traducciones de equipo.
        # (el código de equipo ya no viene en el calendario)
        for eqData in nuevoPartido.Equipos.values():
            self.Calendario.nuevaTraduccionEquipo2Codigo(nombres=eqData['Nombre'], abrev=eqData['abrev'],
                                                         idEq=eqData['id'])

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
        atrs2delete = {'changed'}
        for atributo in atrs2delete:
            if hasattr(aux, atributo):
                delattr(aux, atributo)

        setrecursionlimit(50000)
        # TODO: Protect this
        with open(filename, "wb") as handler:
            dump(aux, handler)

    def cargaTemporada(self, filename):
        # TODO: Protect this
        retry = False
        setUpdatePlantillaFormat = False
        try:
            with open(filename, "rb") as handler:
                aux = load(handler)
        except ModuleNotFoundError:
            # Para compatibilidad hacia atras (ficheros grabados antes de CAPcore)
            sys.modules['Utils.LoggedDict'] = sys.modules['CAPcore.LoggedDict']
            sys.modules['Utils.LoggedValue'] = sys.modules['CAPcore.LoggedValue']
            retry = True
        except AttributeError:
            # Para compatibilidad hacia atras (ficheros grabados antes de revamping de CAPcore.*Logged*)
            sys.modules['CAPcore.LoggedDict'].DictOfLoggedDict = sys.modules['CAPcore.DictLoggedDict'].DictOfLoggedDict
            retry = True
            setUpdatePlantillaFormat = True

        if retry:
            print(f"SMACB.TemporadaACB.TemporadaACB.cargaTemporada: retrying load of '{filename}'")
            with open(filename, "rb") as handler:
                aux = load(handler)

        fields2skip = {'changed', 'tradEquipos'}
        for attr in dir(aux):
            if (attr in fields2skip) or callable(getattr(aux, attr)) or attr.startswith('__'):
                continue
            setattr(self, attr, getattr(aux, attr))

        if setUpdatePlantillaFormat:
            print("SMACB.TemporadaACB.TemporadaACB.cargaTemporada: actualizando clases base de plantillas")
            for idEq, data in self.plantillas.items():
                self.plantillas[idEq] = data.actualizaClasesBase()

        self.Calendario.actualizaDatosPlayoffJornada()  # Para compatibilidad hacia atrás

    def actualizaFichasPartido(self, nuevoPartido, browser=None, config=None):
        browser, config = prepareDownloading(browser, config, URL_BASE)

        refrescaFichas = False

        if 'refresca' in config and config.refresca:
            refrescaFichas = True

        for codJ, datosJug in nuevoPartido.Jugadores.items():
            if codJ in JUGADORESDESCARGADOS:
                continue
            if (codJ not in self.fichaJugadores) or (self.fichaJugadores[codJ] is None):
                try:
                    nuevaFicha = FichaJugador.fromURL(datosJug['linkPersona'], datosPartido=datosJug,
                                                      home=browser.get_url(), browser=browser, config=config)
                    self.fichaJugadores[codJ] = nuevaFicha
                except Exception as exc:
                    print(f"SMACB.TemporadaACB.TemporadaACB.actualizaFichasPartido [{nuevoPartido.url}]: something "
                          f"happened creating record for {codJ}. Datos: {datosJug}", exc)
                    traceback.print_tb(exc.__traceback__)
                    if codJ in JUGADORESDESCARGADOS:
                        JUGADORESDESCARGADOS.remove(codJ)
                    continue

            elif refrescaFichas or (not hasattr(self.fichaJugadores[codJ], 'sinDatos')) or (
                    self.fichaJugadores[codJ].sinDatos is None) or (self.fichaJugadores[codJ].sinDatos):
                urlJugAux = mergeURL(browser.get_url(), datosJug['linkPersona'])
                if urlJugAux != self.fichaJugadores[codJ].URL:
                    self.fichaJugadores[codJ].URL = urlJugAux
                    self.changed = True
                try:
                    self.changed |= self.fichaJugadores[codJ].actualizaFromWeb(datosPartido=datosJug, browser=browser,
                                                                               config=config)
                    JUGADORESDESCARGADOS.add(codJ)
                except Exception as exc:
                    print(f"SMACB.TemporadaACB.TemporadaACB.actualizaFichasPartido [{nuevoPartido.url}]: something "
                          f"happened updating record of {codJ}. Datos: {datosJug}", exc)
                    traceback.print_tb(exc.__traceback__)
                if codJ in JUGADORESDESCARGADOS:
                    JUGADORESDESCARGADOS.remove(codJ)

            self.changed |= self.fichaJugadores[codJ].nuevoPartido(nuevoPartido)

        # TODO: Procesar ficha de entrenadores
        for codE in nuevoPartido.Entrenadores:
            pass

    def actualizaPlantillas(self, browser=None, config=None):
        result = False
        if self.descargaPlantillas:

            browser, config = prepareDownloading(browser, config, URL_BASE)

            datosPlantillas = descargaPlantillasCabecera(browser, config)
            for p_id in datosPlantillas:
                if p_id not in self.plantillas:
                    self.plantillas[p_id] = PlantillaACB(p_id)

                resPlant = self.plantillas[p_id].descargaYactualizaPlantilla(browser=None, config=config)
                result |= resPlant

                self.changed |= result
        return result

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

        listaURLs: List[str] = listaURLPartidos or self.Partidos.keys()

        dfPartidos: List[pd.DataFrame] = [self.Partidos[pURL].jugadoresAdataframe() for pURL in listaURLs]

        dfResult: pd.DataFrame = pd.concat(dfPartidos, axis=0, ignore_index=True, sort=True)

        periodos = auxJorFech2periodo(dfResult)

        dfResult['periodo'] = dfResult.apply(lambda r: periodos[r['jornada']][r['fechaPartido'].date()], axis=1)

        return dfResult

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
        auxEstadisticosDF['A-BP', 'sum'] = auxEstadisticosDF['A', 'sum'] / auxEstadisticosDF['BP', 'sum']
        auxEstadisticosDF['A-TCI', 'sum'] = auxEstadisticosDF['A', 'sum'] / auxEstadisticosDF['TC-I', 'sum']

        auxIdentsDF = estadsJugadoresEq[COLSIDENT].groupby('codigo').tail(n=1).set_index('codigo', drop=False)
        auxIdentsDF.columns = pd.MultiIndex.from_tuples([('Jugador', col) for col in auxIdentsDF.columns])

        result = pd.concat([auxIdentsDF, auxEstadisticosDF], axis=1)
        return result

    def sigPartido(self, abrEq: str) -> infoSigPartido:
        """
        Devuelve el siguiente partido de un equipo y los anteriores y siguientes del equipo y su próximo rival
        :param abrEq: abreviatura del equipo objetivo
        :return: tupla infoSigPartido
        * Información del siguiente partido
        * Tupla con las abrevs del equipo local y visit del siguiente
        * Partidos pasados del eq local
        * Partidos futuros del eq local
        * Partidos pasados del eq visitante
        * Partidos futuros del eq visitante
        * Si la abrev objetivo es local (True) o visit (False)
        """
        juCal, peCal = self.Calendario.partidosEquipo(abrEq)
        peOrd = sorted(list(peCal), key=itemgetter('fechaPartido'))

        juOrdTem = sorted([p['url'] for p in juCal], key=lambda u: self.Partidos[u].fechaPartido)

        sigPart = peOrd.pop(0)
        abrevsEq = self.Calendario.abrevsEquipo(abrEq)
        abrRival = sigPart['participantes'].difference(abrevsEq).pop()
        juRivCal, peRivCal = self.Calendario.partidosEquipo(abrRival)

        peRivOrd = sorted([p for p in peRivCal if p['jornada'] != sigPart['jornada']], key=itemgetter('fechaPartido'))
        juRivTem = sorted([p['url'] for p in juRivCal], key=lambda u: self.Partidos[u].fechaPartido)

        eqIsLocal = sigPart['loc2abrev']['Local'] in abrevsEq
        juIzda, peIzda, juDcha, peDcha = (juOrdTem, peOrd, juRivTem, peRivOrd) if eqIsLocal else (
            juRivTem, peRivOrd, juOrdTem, peOrd)
        resAbrevs = (abrEq, abrRival) if eqIsLocal else (abrRival, abrEq)

        result = infoSigPartido(sigPartido=sigPart, abrevLV=resAbrevs, eqIsLocal=eqIsLocal, jugLocal=juIzda,
                                pendLocal=peIzda, jugVis=juDcha, pendVis=peDcha, )
        return result

    def clasifEquipo(self, abrEq: str, fecha: Optional[Any] = None, gameList: Optional[set[str]] = None
                     ) -> infoClasifEquipo:
        """
        Extrae los datos necesarios para calcular la clasificación (solo liga regular) de un equipo hasta determinada
        fecha
        :param abrEq: Abreviatura del equipo en cuestión, puede ser cualquiera de las que haya tenido
        :param fecha: usar solo los partidos ANTERIORES a la fecha
        :return: diccionario con los datos calculados
        """
        abrevsEq = self.Calendario.abrevsEquipo(abrEq)
        auxResult = defaultdict(int)
        auxResult['Jjug'] = set()
        auxResult['auxCasaFuera'] = {'Local': defaultdict(int), 'Visitante': defaultdict(int)}
        auxResult['CasaFuera'] = dict()
        auxResult['sumaCoc'] = Decimal(0)

        urlGamesFull = self.extractGameList(fecha=fecha, abrevEquipos={abrEq}, playOffStatus=False)
        urlGames = urlGamesFull if gameList is None else urlGamesFull.intersection(gameList)
        partidosAcontar = [self.Partidos[pURL].DatosSuministrados for pURL in urlGames]

        for datosCal in partidosAcontar:
            auxResult['Jjug'].add(int(datosCal['jornada']))

            abrevUsada = abrevsEq.intersection(datosCal['participantes']).pop()
            locEq = datosCal['abrev2loc'][abrevUsada]
            locRival = OtherLoc(locEq)

            datosEq = datosCal['equipos'][locEq]
            datosRival = datosCal['equipos'][locRival]
            claveRes = 'V' if datosEq['haGanado'] else 'D'

            auxResult['Jug'] += 1
            auxResult[claveRes] += 1
            auxResult['auxCasaFuera'][locEq][claveRes] += 1

            auxResult['Pfav'] += datosEq['puntos']
            auxResult['Pcon'] += datosRival['puntos']
            auxResult['sumaCoc'] += (Decimal(datosEq['puntos']) / Decimal(datosRival['puntos'])).quantize(
                Decimal('.001'))

        auxResult['idEq'] = self.Calendario.tradEquipos['c2i'][abrEq]
        auxResult['nombresEq'] = self.Calendario.tradEquipos['c2n'][abrEq]
        auxResult['abrevsEq'] = abrevsEq
        auxResult['nombreCorto'] = sorted(auxResult['nombresEq'], key=len)[0]
        auxResult['abrevAusar'] = abrEq

        for k in ['Jug', 'V', 'D', 'Pfav', 'Pcon']:
            if k not in auxResult:
                auxResult[k] = 0
        for loc in LocalVisitante:
            auxResult['CasaFuera'][loc] = infoClasifBase(**auxResult['auxCasaFuera'][loc])
        auxResult.pop('auxCasaFuera')
        auxResult['ratioVict'] = auxResult['V'] / auxResult['Jug'] if auxResult['Jug'] else 0.0
        result = infoClasifEquipo(**auxResult)
        return result

    def clasifLiga(self, fecha=None, abrevList: Optional[set[str]] = None, parcial: bool = False, datosLR=None) -> list[
        infoClasifEquipo]:
        teamList = abrevList
        if abrevList is None:
            teamList = {onlySetElement(codSet) for codSet in self.Calendario.tradEquipos['i2c'].values()}

        funcKey = entradaClas2kBasic

        gameList = self.extractGameList(fecha=fecha, abrevEquipos=teamList, playOffStatus=False)

        datosClasifEquipos: list[infoClasifEquipo] = [self.clasifEquipo(abrEq=eq, fecha=fecha, gameList=gameList) for eq
                                                      in teamList]

        if datosLR is None:
            datosLR = {x.abrevAusar: x for x in datosClasifEquipos}

        if parcial:  # Grupo de empatados
            numEqs = len(teamList)
            if len(gameList) != numEqs * (numEqs - 1):  # No han jugado todos contra todos I-V
                # Estadistica básica con los partidos de LR
                funcKey = entradaClas2kBasic
                datosClasifEquipos = [datosLR[abrev] for abrev in abrevList]

            else:  # Han jugado todos contra todos I-V
                funcKey = entradaClas2kEmpatePareja if len(teamList) == 2 else entradaClas2kEmpateMasD2
        else:  # Todos los equipos
            partsJug = {i.Jug for i in datosClasifEquipos}
            funcKey = entradaClas2kVict if len(partsJug) == 1 else entradaClas2kRatioVict

        resultInicial = sorted(datosClasifEquipos, key=lambda x: funcKey(x, datosLR), reverse=True)

        resultFinal = []
        agrupClasif = defaultdict(set)
        for datosEq in resultInicial:
            abrev = datosEq.abrevAusar
            kClasif = funcKey(datosEq, datosLR)
            agrupClasif[kClasif].add(abrev)

        for k in sorted(agrupClasif, reverse=True):
            abrevK = agrupClasif[k]
            if len(abrevK) == 1:
                for abrev in abrevK:
                    resultFinal.append(datosLR[abrev])
            else:
                desempate = self.clasifLiga(fecha=fecha, abrevList=abrevK, parcial=True, datosLR=datosLR)
                for sc in desempate:
                    resultFinal.append(datosLR[sc.abrevAusar])

        result = resultFinal
        return result

    def dataFrameFichasJugadores(self, abrEq: Optional[str] = None):
        jugsIter = self.fichaJugadores.keys()
        activos = dorsales = {}
        if (abrEq is not None) and self.descargaPlantillas:
            codEq = self.tradEqAbrev2Id(abrEq)
            jugsIter = self.plantillas[codEq].jugadores.keys()
            dorsales = self.plantillas[codEq].jugadores.extractKey('dorsal', 100)
            activos = self.plantillas[codEq].jugadores.extractKey('activo', False)
        auxdict = {j_id: self.fichaJugadores[j_id].dictDatosJugador() for j_id in jugsIter}

        for jugId, ficha in auxdict.items():
            if self.descargaPlantillas:
                auxdict[jugId]['dorsal'] = dorsales[jugId]
                auxdict[jugId]['Activo'] = activos[jugId]
            else:
                auxdict[jugId]['Activo'] = True

            if ficha['ultPartidoP'] is not None:
                partido = self.Partidos[ficha['ultPartidoP']]
                entradaJug = partido.Jugadores[jugId]
                auxdict[jugId]['ultEquipo'] = entradaJug['equipo']
                auxdict[jugId]['ultEquipoAbr'] = entradaJug['CODequipo']

        auxDF = pd.DataFrame.from_dict(auxdict, orient='index')
        for col in ['fechaNac', 'primPartidoT', 'ultPartidoT']:
            auxDF[col] = pd.to_datetime(auxDF[col])

        return auxDF

    def dataFramePartidosLV(self, listaAbrevEquipos: Iterable[str] = None, fecha: Optional[Any] = None,
                            playOffStatus: Optional[bool] = None
                            ):
        """
        Genera un dataframe LV con los partidos de uno o más equipos hasta determinada fecha
        :param listaAbrevEquipos: si None, son todos los partidos
        :param fecha: si None son todos los partidos (límite duro < )
        :return:
        """
        if listaAbrevEquipos is None:
            lista_urls = self.extractGameList(fecha=fecha, abrevEquipos=None, playOffStatus=playOffStatus)
        else:
            lista_urls = set(chain(
                *[self.extractGameList(fecha=fecha, abrevEquipos={eq}, playOffStatus=playOffStatus) for eq in
                  listaAbrevEquipos]))

        partidos_DFlist = [self.Partidos[pURL].partidoAdataframe() for pURL in lista_urls]
        result = pd.concat(partidos_DFlist)
        return result

    def extractGameList(self, fecha=None, abrevEquipos: Optional[Iterable[str]] = None,
                        playOffStatus: Optional[bool] = None
                        ) -> set[str]:
        """
        Obtiene  una lista de URLs de partidos que cumplen ciertas características
        :param fecha: anteriores (hard limit)  a una fecha
        :param abrevEquipos: abreviatura del equipo. Comportamiento del filtro
                None: de todos los equipos
                1 equipo: solo partidos del equipo
                >1 equipo: partidos de los equipos de la lista ENTRE ELLOS
        :param playOffStatus: filtra si el partido es de LR o PO
                None: todos los partidos
                True: solo partidos de Playoff
                False: solo partidos de LR
        :return: set de URLs de los partidos que cumplen las características (la URL es clave  de TemporadaACB.Partidos
        """

        result_url: set[str] = set(self.Partidos.keys())

        if fecha is None and abrevEquipos is None and playOffStatus is None:  # No filter
            return result_url

        # Genera la lista de partidos a incluir
        if abrevEquipos is not None:
            # Recupera la lista de abreviaturas que de los equipos que puede cambiar (la abrev del equipo)
            # a lo largo de la temporada
            colAbrevList = [self.Calendario.abrevsEquipo(ab) for ab in abrevEquipos]
            colAbrevSet = set()
            for abrSet in colAbrevList:
                colAbrevSet.update(abrSet)

            result_url: set[str] = set()
            # Crea la lista de partidos de aquellos en los que están las abreviaturas
            for pURL, pData in self.Partidos.items():
                if len(abrevEquipos) == 1:
                    if colAbrevSet.intersection(pData.DatosSuministrados['participantes']):
                        result_url.add(pURL)
                else:
                    if len(colAbrevSet.intersection(pData.DatosSuministrados['participantes'])) == 2:
                        result_url.add(pURL)

        result_fecha: set[str] = result_url
        if fecha:
            fecha_formatted = fechaParametro2pddatetime(fecha)
            result_fecha: set[str] = {pURL for pURL in result_url if self.Partidos[pURL].fechaPartido < fecha_formatted}

        result_playOff: set[str] = result_fecha
        if playOffStatus is not None:
            result_playOff: set[str] = set()
            for pURL in result_fecha:
                pData: PartidoACB = self.Partidos[pURL]
                jorPartido = int(pData.jornada)
                if self.Calendario.Jornadas[jorPartido]['esPlayoff'] == playOffStatus:
                    result_playOff.add(pURL)
        result: set[str] = result_playOff

        return result

    def dfPartidosLV2ER(self, partidos: pd.DataFrame, abrEq: str = None):

        finalDFlist = []

        if abrEq:
            idEq = self.tradEqAbrev2Id(abrEq)
            partidosEq = partidos.loc[(partidos['Local', 'id'] == idEq) | (partidos['Visitante', 'id'] == idEq)]

            for esLocal in [True, False]:
                tagEq, tagRival = ('Local', 'Visitante') if esLocal else ('Visitante', 'Local')

                auxDFlocal = partidosEq.loc[(partidosEq['Local', 'id'] == idEq) == esLocal]
                infoDF = auxDFlocal['Info']

                eqDF = auxDFlocal[tagEq]
                rivalDF = auxDFlocal[tagRival]

                auxDF = pd.concat([infoDF, eqDF, rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
                finalDFlist.append(auxDF)
        else:
            for loc in LocalVisitante:
                infoDF = partidos['Info']
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

        resultSinProrogas = auxCalculaEstadsSubDataframe(estadPartidos.drop(columns=COLDROPPER + [colProrrogas]))

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
                result[(eq, kRes, 'sum')] = result[(eq, kC, 'sum')] / result[(eq, kI, 'sum')] * 100.0
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

        for idEq in self.Calendario.tradEquipos['i2c'].values():  # Se usa idEq porque la abr puede cambiar durante temp
            abrevEq = next(iter(idEq))  # Coge una abr cualquiera que corresponda al id. (se usa
            # abrev porque esas son fáciles de asociar a equipos)
            dfPartidosEq = self.dfPartidosLV2ER(dfTodosPartidos, abrevEq)
            dfEstadsAgrEq = self.dfEstadsEquipo(dfPartidosEq, abrEq=abrevEq)
            resultDict[abrevEq] = dfEstadsAgrEq
        result = pd.DataFrame.from_dict(data=resultDict, orient='index').sort_index()

        return result

    def trayectoriaEquipo(self, abrev: str) -> list[filaTrayectoriaEq]:
        """
        Produce una lista con la información de todos los partidos conocidos (jugados o por jugar) de un equipo
        :param abrev: abreviatura del equipo
        :return: lista de partidos.
        """
        auxResultado = list()
        targetAbrevs = self.Calendario.abrevsEquipo(abrev)
        juCal, peCal = self.Calendario.partidosEquipo(abrev)

        def EqCalendario2NT(data: dict) -> infoEqCalendario:
            auxDict = {k: v for k, v in data.items() if k in infoEqCalendario._fields}
            result = infoEqCalendario(**auxDict)
            return result

        for p in juCal + peCal:
            abrevAUsar = (p['participantes'].intersection(targetAbrevs)).pop()
            loc = p['abrev2loc'][abrevAUsar]
            auxEntry = dict()
            auxEntry['fechaPartido'] = p['fechaPartido'] if p['pendiente'] else self.Partidos[p['url']].fechaPartido
            auxEntry['jornada'] = p['jornada']
            auxEntry['cod_edicion'] = p['cod_edicion']
            auxEntry['cod_competicion'] = p['cod_competicion']
            auxEntry['pendiente'] = p['pendiente']

            auxEntry['esLocal'] = loc == 'Local'
            if not p['pendiente']:
                auxEntry['haGanado'] = p['resultado'][loc] > p['resultado'][OtherLoc(loc)]
                auxEntry['resultado'] = infoPartLV(**p['resultado'])
                auxEntry['url'] = p['url']
            auxEntry['abrevEqs'] = infoPartLV(**p['loc2abrev'])

            auxEntry['equipoMe'] = EqCalendario2NT(p['equipos'][loc])
            auxEntry['equipoRival'] = EqCalendario2NT(p['equipos'][OtherLoc(loc)])
            auxResultado.append(filaTrayectoriaEq(**auxEntry))

        result = sorted(auxResultado, key=lambda x: x.fechaPartido)
        return result

    def mergeTrayectoriaEquipos(self, abrevIzda: str, abrevDcha: str, incluyeJugados: bool = True,
                                incluyePendientes: bool = True
                                ) -> list[filaMergeTrayectoria]:
        """
        Devuelve la trayectoria comparada entre 2 equipos para poder hacer una tabla entre ellos
        :param abrevIzda: abreviatura del equipo que aparecerá a la izda (cualquiera)
        :param abrevDcha: abreviatura del equipo que aparecerá a la dcha (cualquiera)
        :param incluyeJugados: True si quiere incluir los partidos ya jugados
        :param incluyePendientes: True si quiere incluir los partidos pendientes
        :return:
        """

        partsIzda = self.trayectoriaEquipo(abrevIzda)
        partsDcha = self.trayectoriaEquipo(abrevDcha)

        def cond2incl(p):
            return (p.pendiente and incluyePendientes) or (not p.pendiente and incluyeJugados)

        partsIzdaAux = [p for p in partsIzda if cond2incl(p)]
        partsDchaAux = [p for p in partsDcha if cond2incl(p)]

        lineas = list()

        abrevsIzda = self.Calendario.abrevsEquipo(abrevIzda)
        abrevsDcha = self.Calendario.abrevsEquipo(abrevDcha)
        abrevsPartido = set().union(abrevsIzda).union(abrevsDcha)

        while (len(partsIzdaAux) + len(partsDchaAux)) > 0:
            bloque = dict()
            bloque['precedente'] = False

            try:
                priPartIzda = partsIzdaAux[0]  # List izda is not empty
            except IndexError:
                dato = partsDchaAux.pop(0)
                bloque['jornada'] = dato.jornada
                bloque['dcha'] = dato
                lineas.append(filaMergeTrayectoria(**bloque))
                continue

            try:
                priPartDcha = partsDchaAux[0]  # List dcha is not empty
            except IndexError:
                dato = partsIzdaAux.pop(0)
                bloque['jornada'] = dato.jornada
                bloque['dcha'] = dato
                lineas.append(filaMergeTrayectoria(**bloque))
                continue

            if priPartIzda.jornada == priPartDcha.jornada:
                bloque['jornada'] = priPartIzda.jornada

                datoI = partsIzdaAux.pop(0)
                datoD = partsDchaAux.pop(0)

                bloque['izda'] = datoI
                bloque['dcha'] = datoD

                abrevsPartIzda = {priPartIzda.abrevEqs.Local, priPartIzda.abrevEqs.Visitante}

                bloque['precedente'] = len(abrevsPartido.intersection(abrevsPartIzda)) == 2

            else:
                if (priPartIzda.fechaPartido, priPartIzda.jornada) < (priPartDcha.fechaPartido, priPartDcha.jornada):
                    bloque['jornada'] = priPartIzda.jornada
                    dato = partsIzdaAux.pop(0)
                    bloque['izda'] = dato
                else:
                    bloque['jornada'] = priPartDcha.jornada
                    dato = partsDchaAux.pop(0)
                    bloque['precedente'] = False
                    bloque['dcha'] = dato

            lineas.append(filaMergeTrayectoria(**bloque))

        return lineas

    @property
    def tradEquipos(self):
        return self.Calendario.tradEquipos

    def tradEqAbrev2Id(self, abrev):
        aux = self.tradEquipos['c2i'][abrev]
        if (len(aux)) == 0:
            self.tradEquipos['c2i'].pop(abrev)
            raise KeyError(f"There is no team with acronym {abrev}")
        result = list(aux)[0]
        return result

    def idEquipos(self):
        return list(self.tradEquipos['i2c'].keys())

    def actualizaFichaJugadoresFromCambiosPlant(self, cambiosClub: Dict[str, CambiosPlantillaTipo], browser=None,
                                                config=None
                                                ) -> bool:
        result = False
        for idClub, cambios in cambiosClub.items():
            timestampPlant = self.plantillas[idClub].timestamp
            if not cambios.jugadores:
                continue
            for jugNuevo, datos in cambios.jugadores.added.items():
                datos['timestamp'] = timestampPlant
                if jugNuevo not in self.fichaJugadores:
                    infoJug = FichaJugador.fromDatosPlantilla(datos, idClub, browser=browser, config=config)
                    if infoJug is not None:
                        self.fichaJugadores[jugNuevo] = infoJug
                        result = True
                    else:
                        print(f"NO INFOJUG {jugNuevo}")
                else:
                    result |= self.fichaJugadores[jugNuevo].actualizaFromPlantilla(datos, idClub)
            for jugQuitado, datos in cambios.jugadores.removed.items():
                print(f"Eliminación de jugadores no contemplada id:{jugQuitado} jugador"
                      f"{self.fichaJugadores[jugQuitado]} idClub: {idClub} {self.plantillas[idClub]}")
            for jugCambiado in cambios.jugadores.changed.keys():
                datos = self.plantillas[idClub].jugadores[jugCambiado]
                datos['timestamp'] = timestampPlant
                if jugCambiado not in self.fichaJugadores:
                    infoJug = FichaJugador.fromDatosPlantilla(datos, idClub, browser=browser, config=config)
                    if infoJug is not None:
                        self.fichaJugadores[jugCambiado] = infoJug
                        result = True
                    else:
                        print(f"NO INFOJUG {jugCambiado}")
                else:
                    result |= self.fichaJugadores[jugCambiado].actualizaFromPlantilla(datos, idClub)

        return result


def calculaTempStats(datos, clave, filtroFechas=None):
    if clave not in datos:
        raise KeyError(f"Clave '{clave}' no está en datos.")

    datosWrk = datos
    if filtroFechas:  # TODO: Qué hacer con el filtro
        datosWrk = datos

    agg = datosWrk.set_index('codigo')[clave].astype('float64').groupby('codigo').agg(
        ['mean', 'std', 'count', 'median', 'min', 'max', 'skew'])
    agg1 = agg.rename(columns=dict((x, clave + "-" + x) for x in agg.columns)).reset_index()
    return agg1


def calculaZ(datos, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    finalKeys = ['codigo', 'competicion', 'temporada', 'jornada', 'CODequipo', 'CODrival', 'esLocal', 'haJugado',
                 'fechaPartido', 'periodo', clave]
    finalTypes = {'CODrival': 'category', 'esLocal': 'bool', 'CODequipo': 'category', ('half-' + clave): 'bool',
                  ('aboveAvg-' + clave): 'bool', (clZ + '-' + clave): 'float64'}
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
    result = {}

    for combN, combV in combs.items():
        combfloat = combV + [(clZ + '-' + clave)]
        resfloat = datos[combfloat].groupby(combV).agg(['mean', 'std', 'count', 'min', 'median', 'max', 'skew'])
        combbool = combV + [('half-' + clave), ('aboveAvg-' + clave)]
        resbool = datos[combbool].groupby(combV).agg(['mean'])
        result[combN] = pd.concat([resbool, resfloat], axis=1, sort=True).reset_index()
        newColNames = [((combN + "-" + colAdpt.get(x, x)) if clave in x else x) for x in
                       combinaPDindexes(result[combN].columns)]
        result[combN].columns = newColNames
        result[combN]["-".join([combN, clave, (clZ.lower() + "Min")])] = (
                result[combN]["-".join([combN, clZ, clave, 'mean'])] - result[combN][
            "-".join([combN, clZ, clave, 'std'])])
        result[combN]["-".join([combN, clave, (clZ.lower() + "Max")])] = (
                result[combN]["-".join([combN, clZ, clave, 'mean'])] + result[combN][
            "-".join([combN, clZ, clave, 'std'])])

    return result


def entradaClas2kVict(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = ent.V
    return result


def entradaClas2kRatioVict(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = ent.ratioVict
    return result


def entradaClas2kBasic(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = (ent.V, ent.ratioVict, ent.Pfav - ent.Pcon, ent.Pfav, ent.sumaCoc)
    return result


def entradaClas2kEmpatePareja(ent: infoClasifEquipo, datosLR: dict) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.abrevAusar]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'LRDifP': auxLR.Pfav - auxLR.Pcon,
           'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplPareja(**aux)

    return result


def entradaClas2kEmpateMasD2(ent: infoClasifEquipo, datosLR: dict) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.abrevAusar]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'EmpPfav': ent.Pfav,
           'LRDifP': auxLR.Pfav - auxLR.Pcon, 'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplMasD2(**aux)

    return result


def esEstCreciente(estName: str, catsCrecientes: set | dict | list | None = None, meother: str = "Eq"):
    """
    Devuelve si una columna de estadísticas es ascendente (mejor cuanto menos) o no
    :param estName: Nombre del estadístico a comprobar (de una lista)
    :param catsCrecientes: lista de estadísticos que son ascendentes (mejor cuanto menos: puntos encajados o balones
    perdidos)
    :param meother: si se trata de mi equipo o del rival (invierte el orden)
    :return: bool
    """
    auxCreciente = {} if catsCrecientes is None else catsCrecientes
    return (meother == "Eq") == (estName in auxCreciente)


def esEstIgnorable(col: tuple, estadObj: str = 'mean', cats2ignore: Iterable | None = None):
    auxCats2Ignore = {} if cats2ignore is None else cats2ignore

    kEq, kMagn, kEst = col

    return (kEst != estadObj) or (kEq == 'Info') or (kMagn in auxCats2Ignore)


def calculaEstadsYOrdenLiga(dataTemp: TemporadaACB, fecha: Any | None = None, estadObj: str = 'mean',
                            catsAscending: Iterable | None = None, cats2ignore: Iterable | None = None
                            ):
    paramMethod = 'min'
    paramNAoption = {True: 'top', False: 'bottom'}

    colList = list()
    targetCols = defaultdict(list)

    auxCats2Ignore = {} if cats2ignore is None else cats2ignore

    dfEstads: pd.DataFrame = dataTemp.dfEstadsLiga(fecha=fecha)

    for col in dfEstads.columns:
        kEq, kMagn, _ = col

        if esEstIgnorable(col, estadObj=estadObj, cats2ignore=auxCats2Ignore):
            continue

        colList.append(col)
        isAscending = esEstCreciente(kMagn, catsAscending, kEq)

        targetCols[isAscending].append(col)

    rankDF = dict()
    for asctype in targetCols:
        interestingCols = targetCols[asctype]
        auxDF = dfEstads[interestingCols]
        auxDFranks = auxDF.rank(axis=0, method=paramMethod, na_option=paramNAoption[asctype], ascending=asctype)
        rankDF[asctype] = auxDFranks

    result = dfEstads[colList]
    resultRank = pd.concat(rankDF.values(), axis=1)[colList]

    return result, resultRank


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

    nombre = rivalAbr if usaAbr else sorted(tempData.Calendario.tradEquipos['c2n'][rivalAbr], key=len)[ordenNombre]

    result = f"{prefLoc}{nombre}"

    return result


def equipo2clasif(clasifLiga, abrEq):
    result = None

    for eqData in clasifLiga:
        if abrEq in eqData.abrevsEq:
            return eqData

    return result


def extraeCampoYorden(estads: pd.DataFrame, estadsOrden: pd.DataFrame, eq: str = 'eq', clave: str = 'P',
                      estadistico='mean'
                      ):
    targetCol = (eq, clave, estadistico)

    if targetCol not in estads.index:
        valCorrectos = ", ".join(sorted(estads.index).map(str))
        raise KeyError(f"extraeCampoYorden: parametros para dato '{targetCol}' desconocidos. Referencias válidas: "
                       f"{valCorrectos}")

    valor = estads.loc[targetCol]
    orden = estadsOrden.loc[targetCol]

    return valor, orden

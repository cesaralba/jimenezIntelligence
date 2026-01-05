"""
Created on Jan 4, 2018

@author: calba
"""
import logging
import sys
from argparse import Namespace
from collections import defaultdict
from copy import copy
from itertools import chain
from operator import itemgetter
from pickle import dump, load
from sys import setrecursionlimit
from typing import Any, Iterable, Dict, Tuple, List, Set
from typing import Optional

import numpy as np
import pandas as pd
from CAPcore.LoggedDict import LoggedDictDiff, LoggedDict
from CAPcore.LoggedValue import extractValue
from CAPcore.Misc import getUTC
from CAPcore.Web import mergeURL
from mechanicalsoup import StatefulBrowser
from requests import HTTPError

from Utils.FechaHora import fechaParametro2pddatetime
from Utils.Web import prepareDownloading, browserConfigData
from .CalendarioACB import calendario_URLBASE, CalendarioACB
from .Constants import (EqRival, filaMergeTrayectoria, filaTrayectoriaEq, infoEqCalendario, infoPartLV, infoSigPartido,
                        LocalVisitante, OtherLoc, OtherTeam, infoJornada, URL_BASE, )
from .FichaPersona import CAMBIOSENTRENADORES, FichaEntrenador, CAMBIOSJUGADORES, FichaJugador
from .PartidoACB import PartidoACB
from .PlantillaACB import descargaPlantillasCabecera, PlantillaACB, CAMBIOSCLUB, CambiosPlantillaTipo
from .TemporadaEstads import auxCalculaEstadsSubDataframe

logger = logging.getLogger()

DEFAULTNAVALUES = {('Eq', 'convocados', 'sum'): 0, ('Eq', 'utilizados', 'sum'): 0, ('Info', 'prorrogas', 'count'): 0,
                   ('Info', 'prorrogas', 'max'): 0, ('Info', 'prorrogas', 'mean'): 0,
                   ('Info', 'prorrogas', 'median'): 0, ('Info', 'prorrogas', 'min'): 0, ('Info', 'prorrogas', 'std'): 0,
                   ('Info', 'prorrogas', 'sum'): 0, ('Rival', 'convocados', 'sum'): 0,
                   ('Rival', 'utilizados', 'sum'): 0, }

JUGADORESDESCARGADOS = set()
TECNICOSDESGARGADOS = set()

AUXCAMBIOSJUG = CAMBIOSJUGADORES  # For the sake of formatter
AUXCAMBIOSENT = CAMBIOSENTRENADORES  # For the sake of formatter

CAMBIOSCALENDARIO: Optional[LoggedDictDiff] = None


def auxJorFech2periodo(dfTemp: pd.DataFrame):
    periodoAct: int = 0
    jornada = {}
    claveMin = {}
    claveMax = {}
    curVal: Optional[Tuple[Any, str]] = None
    jf2periodo = defaultdict(lambda: defaultdict(int))

    dfPairs: List[Tuple[Any, str]] = dfTemp.apply(lambda r: (r['fechaPartido'].date(), r['jornada']), axis=1).unique()
    for p in sorted(dfPairs):
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
    Calendario: CalendarioACB

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

        self.timestamp = getUTC()
        self.Calendario = CalendarioACB(competicion=self.competicion, edicion=self.edicion, urlbase=self.urlbase)
        self.Partidos: Dict[str, PartidoACB] = {}
        self.changed: bool = False
        self.tradJugadores = {'id2nombres': defaultdict(set), 'nombre2ids': defaultdict(set)}
        self.descargaFichas: bool = descargaFichas
        self.descargaPlantillas: bool = descargaPlantillas
        self.fichaJugadores: Dict[str, FichaJugador] = {}
        self.fichaEntrenadores: Dict[str, FichaEntrenador] = {}
        self.plantillas: Dict[str, PlantillaACB] = {}
        self.calendarioDict: LoggedDict = LoggedDict(timestamp=self.timestamp)

    def __repr__(self):
        tstampStr = self.timestamp.strftime("%Y%m%d-%H:%M:%S")
        result = f"{self.competicion} Temporada: {self.edicion} Datos: {tstampStr}"
        return result

    __str__ = __repr__

    def getConfig(self) -> Namespace:
        result = Namespace(**{'procesaBio': self.descargaFichas, 'procesaPlantilla': self.descargaPlantillas})
        return result

    def actualizaTemporada(self, home=None, browser=None, config=None):
        interrupted = False
        changeOrig = self.changed

        browser, config = prepareDownloading(browser, config)

        self.Calendario.actualizaCalendario(browser=browser, config=config)
        self.Calendario.actualizaDatosPlayoffJornada()  # Para compatibilidad hacia atrás
        self.changed |= self.buscaCambiosCalendario()

        partidosABajar = sorted(set(self.Calendario.Partidos.keys()).difference(set(self.Partidos.keys())))
        partidosABajar = limitaPartidosBajados(config, partidosABajar)
        partidosBajados: Set[str] = set()

        try:
            for partido in partidosABajar:
                try:
                    partidoDescargado = PartidoACB(**(self.Calendario.Partidos[partido]))
                    partidoDescargado.descargaPartido(home=home, browser=browser, config=config)
                    if not partidoDescargado.check():
                        continue
                    self.actualizaInfoAuxiliar(nuevoPartido=partidoDescargado, browser=browser, config=config)
                    self.Partidos[partido] = partidoDescargado
                    partidosBajados.add(partido)

                except KeyboardInterrupt as exc:
                    logging.info("actualizaTemporada: interrumpida ejecución descargando  partido '%s'", partido)
                    raise KeyboardInterrupt from exc
                except BaseException:
                    logging.exception("actualizaTemporada: problemas descargando  partido '%s'", partido)

        except KeyboardInterrupt:
            logging.info("actualizaTemporada: Ejecución terminada por el usuario")
            interrupted = True

        self.changed |= (len(partidosBajados) > 0)

        if not interrupted:
            if self.descargaPlantillas:
                resPlant = self.actualizaPlantillasConDescarga(browser=browser, config=config)
                self.changed |= resPlant
                if resPlant:
                    self.changed |= self.actualizaFichaJugadoresFromCambiosPlant(CAMBIOSCLUB)
            else:
                resPlant = self.actualizaPlantillasSinDescarga()
                self.changed |= resPlant

        if self.changed != changeOrig:
            self.timestamp = getUTC()

        return partidosBajados

    def actualizaInfoAuxiliar(self, nuevoPartido: PartidoACB, browser, config):
        self.actualizaNombresEquipo(nuevoPartido)
        if not getattr(config, 'procesaPlantilla', False):
            self.changed |= self.creaPlantillasDesdePartidoSinDesc(nuevoPartido=nuevoPartido)

        self.changed |= self.actualizaFichasPartido(nuevoPartido, browser=browser, config=config)
        if not getattr(config, 'procesaPlantilla', False):
            self.changed |= self.actualizaPlantillasDesdePartidoSinDesc(nuevoPartido=nuevoPartido)

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

    def grabaTemporada(self, filename: str):
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
        self.changed |= self.actualizaClase()

    def actualizaFichasPartido(self, nuevoPartido: PartidoACB, browser=None, config=None) -> bool:

        changes = False
        if self.descargaFichas:
            changes |= self.actualizaFichasPartidoConDesc(nuevoPartido, browser, config)
        else:
            changes |= self.actualizaFichasPartidoSinDesc(partido=nuevoPartido, config=config)

        return changes

    def actualizaFichasPartidoConDesc(self, nuevoPartido: PartidoACB, browser: Optional[StatefulBrowser] = None,
                                      config: Optional[Namespace | Dict] = None) -> bool:

        browser, config = prepareDownloading(browser, config)
        refrescaFichas = getattr(config, 'refresca', False)

        for codJ, datosJug in nuevoPartido.Jugadores.items():
            if codJ in JUGADORESDESCARGADOS:
                self.changed |= self.fichaJugadores[codJ].nuevoPartido(nuevoPartido)
                continue

            if not self.fichaJugadores.get(codJ, None):
                try:
                    urlJug = mergeURL(URL_BASE, datosJug['linkPersona'])
                    nuevaFicha = FichaJugador.fromURL(urlJug, datos=datosJug,
                                                      home=browser.get_url(), browser=browser, config=config)
                    self.fichaJugadores[codJ] = nuevaFicha
                    JUGADORESDESCARGADOS.add(codJ)
                    self.changed = True
                except HTTPError:
                    logging.exception("Partido [%s]: something happened creating record for %s. Datos: %s",
                                      nuevoPartido.url, codJ, datosJug)
                    nuevaFicha = FichaJugador.fromPartido(idPersona=codJ, datos=datosJug,
                                                          timestamp=nuevoPartido.timestamp)
                    self.fichaJugadores[codJ] = nuevaFicha
                    JUGADORESDESCARGADOS.add(codJ)
                    self.changed = True
            elif refrescaFichas or getattr(self.fichaJugadores[codJ], 'sindatos', True):
                try:
                    self.changed |= self.fichaJugadores[codJ].actualizaFromWeb(datosPartido=datosJug,
                                                                               browser=browser,
                                                                               config=config)
                    JUGADORESDESCARGADOS.add(codJ)
                except HTTPError:
                    logging.exception("Partido [%s]: something happened updating record for %s. Datos: %s",
                                      nuevoPartido.url, codJ, datosJug)

                self.changed |= self.fichaJugadores[codJ].nuevoPartido(nuevoPartido)

            self.changed |= self.fichaJugadores[codJ].nuevoPartido(nuevoPartido)

    def actualizaFichasPartidoSinDesc(self, partido: PartidoACB):
        changes: bool = False

        for codJ, datosJug in partido.Jugadores.items():
            if codJ in JUGADORESDESCARGADOS:
                changes |= self.fichaJugadores[codJ].nuevoPartido(partido)
                continue

            if codJ not in self.fichaJugadores:
                nuevaFicha = FichaJugador.fromPartido(idPersona=codJ, datosPartido=datosJug,
                                                      timestamp=partido.timestamp)
                self.fichaJugadores[codJ] = nuevaFicha
                changes |= True
                JUGADORESDESCARGADOS.add(codJ)

            changes |= self.fichaJugadores[codJ].nuevoPartido(partido)

        for codE, datosEnt in partido.Entrenadores.items():
            if codE in TECNICOSDESGARGADOS:
                changes |= self.fichaEntrenadores[codE].nuevoPartido(partido)
                continue

            if codE not in self.fichaJugadores:
                if datosEnt['dorsal'] == 'E':
                    datosEnt['dorsal'] = '1'

                nuevaFicha = FichaEntrenador.fromPartido(idPersona=codE, datosPartido=datosEnt,
                                                         timestamp=partido.timestamp)
                self.fichaEntrenadores[codE] = nuevaFicha
                changes |= True
                TECNICOSDESGARGADOS.add(codE)

            changes |= self.fichaEntrenadores[codE].nuevoPartido(partido)

        return changes

    def creaPlantillasDesdePartidoSinDesc(self, nuevoPartido: PartidoACB) -> bool:
        """
        Como no descargamos la plantilla (por configuración), hay que hacer operaciones como sí. En este caso se crea la
        plantilla si no existe ya a partir de los datos que vienen en los partidos.
        :param nuevoPartido:
        :return:
        """
        auxChanged = False
        for eq in nuevoPartido.Equipos.values():
            eqId = eq['id']
            if eqId in self.plantillas:
                continue
            self.plantillas[eqId] = PlantillaACB(eqId, edicion=self.edicion)
            auxChanged = True
            dataClub = {'club': {'nombreActual': eq['Nombre'], 'nombreOficial': eq['Nombre']}}
            self.plantillas[eqId].actualizaPlantillaDescargada(dataClub)
        return auxChanged

    def actualizaPlantillasDesdePartidoSinDesc(self, nuevoPartido: PartidoACB) -> bool:
        auxChanged = False
        for loc, eq in nuevoPartido.Equipos.items():
            eqId = eq['id']
            plantillaActivos = self.plantillas[eqId].getCurrentDict(soloActivos=True)
            plantillaActual = self.plantillas[eqId].getCurrentDict(soloActivos=False)

            dataPlantAux = nuevoPartido.generaPlantillaDummy(loc, plantillaActual)
            auxChanged |= self.plantillas[eqId].actualizaPlantillaDescargada(dataPlantAux)

        return auxChanged

    def actualizaPlantillasConDescarga(self, browser=None, config=None) -> bool:
        result = False

        browser, config = prepareDownloading(browser, config)
        logger.info("%s Actualizando plantillas", self)
        datosPlantillas = descargaPlantillasCabecera(browser, config)
        for p_id in datosPlantillas:
            if p_id not in self.plantillas:
                self.plantillas[p_id] = PlantillaACB(p_id, edicion=self.edicion)

            resPlant = self.plantillas[p_id].descargaYactualizaPlantilla(browser=None, config=config)
            result |= resPlant

            self.changed |= result

        return result

    def actualizaPlantillasSinDescarga(self) -> bool:
        result = False

        logger.info("%s Actualizando plantillas", self)

        for p_id in self.tradEquipos['i2n']:
            if p_id not in self.plantillas:
                nombresClub = sorted(self.tradEquipos['i2n'][p_id], key=len)
                self.plantillas[p_id] = PlantillaACB(p_id, edicion=self.edicion, **{
                    'club': {'nombreActual': nombresClub[0], 'nombreOficial': nombresClub[-1]}})
                result = True

        self.changed |= result

        return result

    def actualizaTraduccionesJugador(self, nuevoPartido):
        for codJ, datosJug in nuevoPartido.Jugadores.items():
            if codJ in self.fichaJugadores:
                ficha = self.fichaJugadores[codJ]

                self.tradJugadores['nombre2ids'][extractValue(ficha.nombre)].add(ficha.persId)
                self.tradJugadores['nombre2ids'][extractValue(ficha.alias)].add(ficha.persId)
                self.tradJugadores['id2nombres'][ficha.persId].add(extractValue(ficha.nombre))
                self.tradJugadores['id2nombres'][ficha.persId].add(extractValue(ficha.alias))

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
            auxCalculaEstadsSubDataframe, include_groups=False)

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
        peOrd = sorted(peCal, key=itemgetter('fechaPartido'))

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
                rivalDF = auxDFlocal[tagRival]

                auxDF = pd.concat([infoDF, auxDFlocal[tagEq], rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
                finalDFlist.append(auxDF)
        else:
            for loc in LocalVisitante:
                infoDF = partidos['Info']
                rivalDF = partidos[OtherLoc(loc)]

                auxDF = pd.concat([infoDF, partidos[loc], rivalDF], axis=1, keys=['Info', 'Eq', 'Rival'])
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
            for eq in EqRival:
                result[(eq, f'T{k}%', 'sum')] = result[(eq, f'T{k}-C', 'sum')] / result[(eq, f'T{k}-I', 'sum')] * 100.0
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

        resultDict = {}
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
        auxResultado = []
        targetAbrevs = self.Calendario.abrevsEquipo(abrev)
        juCal, peCal = self.Calendario.partidosEquipo(abrev)

        def EqCalendario2NT(data: dict) -> infoEqCalendario:
            auxDict = {k: v for k, v in data.items() if k in infoEqCalendario._fields}
            result = infoEqCalendario(**auxDict)
            return result

        for p in juCal + peCal:
            abrevAUsar = (p['participantes'].intersection(targetAbrevs)).pop()
            loc = p['abrev2loc'][abrevAUsar]
            auxEntry = {}
            auxEntry['fechaPartido'] = p['fechaPartido'] if p['pendiente'] else self.Partidos[p['url']].fechaPartido
            auxEntry['infoJornada'] = p['infoJornada'] if p['pendiente'] else Partido2InfoJornada(
                self.Partidos[p['url']], self)
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

    def mergeTrayectoriaEquipos(self, abrevIzda: str, abrevDcha: str,
                                **kwargs) -> Tuple[list[filaMergeTrayectoria], str]:
        """
        Devuelve la trayectoria comparada entre 2 equipos para poder hacer una tabla entre ellos
        :param abrevIzda: abreviatura del equipo que aparecerá a la izda (cualquiera)
        :param abrevDcha: abreviatura del equipo que aparecerá a la dcha (cualquiera)
        :param incluyeJugados: True si quiere incluir los partidos ya jugados
        :param incluyePendientes: True si quiere incluir los partidos pendientes
        :param limitRows: None si quiere limitar el número de líneas que aparecen en la trayectoria de los equipos
                               None -> no se recorta
                               número de líneas a mostrar -> El recorte elimina líneas más antiguas que no sean
                                  antecedentes de partidos entre los 2 equipos. Hace lo que puede, si en el número no
                                  caben todas las líneas que tienen que estar (antecedentes y partidos pendientes), los
                                  mantiene y pone un mensaje de error que puede usarse como aviso en el programa
        :return:
            trayectorias: lista de líneas con la evolución de los partidos de los 2 equipos a lo largo de la temporada
            mensaje: mensaje de aviso si relativo al recorte a limitRows: si sucedió o si hubo problemas para hacerlo
        """

        limitRows: Optional[int] = kwargs.get('limitRows', None)

        lineas = mezclaTrayectoriaEquipos(self, abrevDcha, abrevIzda, **kwargs)

        mensajeAviso = ""
        if limitRows is None or limitRows >= len(lineas):
            return lineas, mensajeAviso

        result, mensajeAviso = limitaLineasEnTrayectoriaEquipos(limitRows, lineas)

        result.reverse()

        return result, mensajeAviso

    @property
    def tradEquipos(self):
        return self.Calendario.tradEquipos

    def jornadasCompletas(self):
        return self.Calendario.jornadasCompletas()

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
            browserConfig = browserConfigData(browser=browser, config=config,
                                              timestamp=self.plantillas[idClub].timestamp)
            if not cambios.jugadores:
                continue
            for jugQuitado, datos in cambios.jugadores.removed.items():
                # TODO: Qué hacer con los eliminados?
                print(f"Eliminación de jugadores no contemplada id:{jugQuitado} jugador"
                      f"{self.fichaJugadores[jugQuitado]} idClub: {idClub} {self.plantillas[idClub]} {datos}")
            result |= self.actualizaFichaJugadoresNuevos(cambios=cambios, idClub=idClub, brwCfg=browserConfig)
            result |= self.actualizaFichaJugadoresCambiados(cambios=cambios, idClub=idClub, brwCfg=browserConfig)

        return result

    def actualizaFichaJugadoresCambiados(self, cambios, idClub, brwCfg: browserConfigData):
        result = False
        for jugCambiado in cambios.jugadores.changed.keys():
            datos = self.plantillas[idClub].jugadores[jugCambiado]
            datos['timestamp'] = brwCfg.timestamp
            if jugCambiado not in self.fichaJugadores:
                infoJug = FichaJugador.fromDatosPlantilla(datos, idClub, browser=brwCfg.browser, config=brwCfg.config)
                if infoJug is not None:
                    self.fichaJugadores[jugCambiado] = infoJug
                    result = True
                else:
                    print(f"NO INFOJUG {jugCambiado}")
            else:
                result |= self.fichaJugadores[jugCambiado].actualizaFromPlantilla(datos, idClub)
        return result

    def actualizaFichaJugadoresNuevos(self, cambios, idClub, brwCfg: browserConfigData):
        result = False
        for jugNuevo, datos in cambios.jugadores.added.items():
            datos['timestamp'] = brwCfg.timestamp
            if jugNuevo not in self.fichaJugadores:
                infoJug = FichaJugador.fromDatosPlantilla(datos, idClub, browser=brwCfg.browser, config=brwCfg.config)
                if infoJug is not None:
                    self.fichaJugadores[jugNuevo] = infoJug
                    result = True
                else:
                    print(f"NO INFOJUG {jugNuevo}")
            else:
                result |= self.fichaJugadores[jugNuevo].actualizaFromPlantilla(datos, idClub)
        return result

    def calendario2dict(self):
        result = {}
        auxCalendDict = self.Calendario.cal2dict()
        result.update(auxCalendDict['pendientes'])
        result.update(auxCalendDict['jugados'])

        return result

    def actualizaClase(self):
        """
        Añade atributos no existentes cuando se creó el fichero y los carga con valores razonables
        :return: True si hubo cambios en la clase que necesiten ser grabados (para actualizar self.changed)
        """
        result = False

        if not hasattr(self, 'calendarioDict'):
            setattr(self, 'calendarioDict', LoggedDict(timestamp=self.timestamp))
        if len(self.calendarioDict) == 0:
            result |= self.calendarioDict.replace(self.calendario2dict())

        return result

    def buscaCambiosCalendario(self):
        # pylint: disable=global-statement
        global CAMBIOSCALENDARIO
        # pylint: enable=global-statement

        calActualDict = self.calendario2dict()
        CAMBIOSCALENDARIO = self.calendarioDict.diff(calActualDict)

        return self.calendarioDict.replace(calActualDict)


def cargaTemporada(fname: str) -> TemporadaACB:
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def Partido2InfoJornada(part: PartidoACB, temp: TemporadaACB) -> infoJornada:
    if hasattr(part, 'infoJornada') and part.infoJornada is not None:
        return part.infoJornada
    return temp.Calendario.Jornadas[part.jornada]['infoJornada']


def mezclaTrayectoriaEquipos(dataTemp: TemporadaACB, abrevDcha, abrevIzda, **kwargs):
    def cond2incl(p):
        return (p.pendiente and kwargs.get('incluyePendientes', True)) or (
                not p.pendiente and kwargs.get('incluyeJugados', True))

    partsIzdaAux = [p for p in dataTemp.trayectoriaEquipo(abrevIzda) if cond2incl(p)]
    partsDchaAux = [p for p in dataTemp.trayectoriaEquipo(abrevDcha) if cond2incl(p)]
    lineas = []
    abrevsPartido = set().union(dataTemp.Calendario.abrevsEquipo(abrevIzda)).union(
        dataTemp.Calendario.abrevsEquipo(abrevDcha))
    while (len(partsIzdaAux) + len(partsDchaAux)) > 0:
        bloque: Dict[str, Any] = {'precedente': False, 'pendiente': False}

        try:
            priPartIzda = partsIzdaAux[0]  # List izda is not empty
        except IndexError:
            dato = partsDchaAux.pop(0)
            bloque.update({'jornada': dato.jornada, 'infoJornada': dato.infoJornada, 'dcha': dato})
            bloque['pendiente'] |= dato.pendiente
            lineas.append(filaMergeTrayectoria(**bloque))
            continue

        try:
            priPartDcha = partsDchaAux[0]  # List dcha is not empty
        except IndexError:
            dato = partsIzdaAux.pop(0)
            bloque.update({'jornada': dato.jornada, 'infoJornada': dato.infoJornada, 'izda': dato})
            bloque['pendiente'] |= dato.pendiente
            lineas.append(filaMergeTrayectoria(**bloque))
            continue

        if priPartIzda.jornada == priPartDcha.jornada:
            datoI = partsIzdaAux.pop(0)
            datoD = partsDchaAux.pop(0)
            bloque.update(
                {'jornada': datoI.jornada, 'infoJornada': datoI.infoJornada, 'izda': datoI, 'dcha': datoD})
            bloque['pendiente'] |= priPartIzda.pendiente | priPartDcha.pendiente
            bloque['precedente'] = len(
                abrevsPartido.intersection({priPartIzda.abrevEqs.Local, priPartIzda.abrevEqs.Visitante})) == 2
        else:
            bloque['precedente'] = False
            if (priPartIzda.fechaPartido, priPartIzda.jornada) < (priPartDcha.fechaPartido, priPartDcha.jornada):
                dato = partsIzdaAux.pop(0)
                bloque.update(
                    {'jornada': priPartIzda.jornada, 'infoJornada': priPartIzda.infoJornada, 'izda': dato})
                bloque['pendiente'] |= priPartIzda.pendiente
            else:
                dato = partsDchaAux.pop(0)
                bloque.update(
                    {'jornada': priPartDcha.jornada, 'infoJornada': priPartDcha.infoJornada, 'izda': dato})
                bloque['pendiente'] |= priPartDcha.pendiente
                bloque['dcha'] = dato

        lineas.append(filaMergeTrayectoria(**bloque))
    return lineas


def limitaLineasEnTrayectoriaEquipos(limitRows, lineas):
    mensajeAviso = ""
    result = []
    quedan = limitRows
    for revGame in reversed(lineas):
        data: filaMergeTrayectoria = revGame
        if data.pendiente or data.precedente:
            if quedan > 0:  # Hay sitio -> p'adentro
                result.append(data)
                quedan -= 1
                continue
            if quedan == 0:  # No hay sitio, quitamos una fila que no sea ni precedente ni partido pendiente
                for insrow in reversed(result):
                    if not (insrow.pendiente or insrow.precedente):
                        result.remove(insrow)
                        result.append(data)
                        break
                else:  # No hay nada que eliminar, se añade en cualquier caso y se pone un aviso
                    # Como solo se produce cuando hay 0 el mensaje sólo se pone una vez
                    result.append(data)
                    quedan -= 1
                    mensajeAviso = ("La pagina no puede contener el número mínimo de resultados. "
                                    "El formato puede descuadrarse")
                    print(mensajeAviso)
                    continue
            else:  # No hay sitio pero se añada aunque se descaraje el formato
                result.append(data)
                quedan -= 1

            print(f"Pendiente: {quedan}")
            continue
        # Filas prescindibles.
        if quedan > 0:  # Hay sitio -> p'adentro
            result.append(data)
            quedan -= 1
        else:  # No hay sitio, poner aviso en la tabla
            if mensajeAviso == "":
                mensajeAviso = "Filas de trayectoria eliminadas por tamaño de página"
    return result, mensajeAviso


def limitaPartidosBajados(config: Namespace, partidosABajar: List[str]) -> List[str]:
    maxPartidosABajar = 1 if (config.justone and not config.limit) else config.limit
    if maxPartidosABajar:
        partidosABajar = partidosABajar[:maxPartidosABajar]
    return partidosABajar

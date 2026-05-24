import logging
import re
from compression import zstd
from itertools import product
from pickle import dumps, loads
from time import gmtime
from typing import Optional, Dict, Tuple, Union, List

import numpy as np
import pandas as pd
from CAPcore.Misc import BadParameters
from CAPcore.Web import downloadPage, DownloadedPage, mergeURL
from bs4 import Tag

from Utils.ProcessMDparts import procesaMDresInfoPeriodos, procesaMDresEstadsCompar, procesaMDresInfoRachas, \
    procesaMDresCartaTiro, procesaMDjugadas, jugadaSort, jugada2str, jugadaKey2sort, jugadaTag2Desc, jugadaKey2str, \
    procesaMDboxscore, procesaMDavailableContent, procesaMDresDatosPartido
from Utils.Web import prepareDownloading, extraePagDataScripts, getIDfromEncURL
from .Constants import (bool2esp, haGanado2esp, local2esp, LocalVisitante, OtherLoc, titular2esp, infoJornada,
                        POLABEL2FASE, DEFTZ, URL_BASE)


class PartidoACB():

    def __init__(self, **kwargs):
        self.jornada = None
        self.infoJornada: Optional[infoJornada] = None
        self.fechaPartido = None
        self.Pabellon = None
        self.Asistencia = None
        self.Arbitros = []
        self.ResultadosParciales = []
        self.prorrogas = 0
        self.timestamp = None
        self.esPlayoff: bool = False

        self.Equipos = {x: {'Jugadores': []} for x in LocalVisitante}

        self.Jugadores = {}
        self.Entrenadores = {}
        self.pendientes: Dict[str, List] = dict.fromkeys(LocalVisitante, [])
        self.aprendidos: Dict[str, List] = dict.fromkeys(LocalVisitante, [])
        self.metadataEnlaces: dict = kwargs.get('enlaces', {})
        self.availMD = {}
        self.metadataEmb: Optional[bytes] = None

        self.EquiposCalendario = kwargs['equipos']
        self.ResultadoCalendario = kwargs['resultado']
        self.CodigosCalendario = kwargs['loc2abrev']

        self.VictoriaLocal = None

        self.DatosSuministrados = kwargs

        self.url = kwargs['url']

        self.competicion = kwargs['cod_competicion']
        self.temporada = kwargs['cod_edicion']
        self.idPartido: str = kwargs.get('partido', None)

        for loc in LocalVisitante:
            self.Equipos[loc]['haGanado'] = self.ResultadoCalendario[loc] > self.ResultadoCalendario[OtherLoc(loc)]

    def descargaPartido(self, home=None, browser=None, config=None):

        browser, config = prepareDownloading(browser, config)

        if not hasattr(self, 'url'):
            raise BadParameters("PartidoACB: DescargaPartido: imposible encontrar la URL del partido")

        urlPartido = self.url

        partidoPage = downloadPage(urlPartido, home=home, browser=browser, config=config)

        self.descargaEmbMetadata(home=home, browser=browser, config=config)

        self.procesaPartido(partidoPage)

    def procesaPartido(self, content: DownloadedPage):
        self.timestamp = getattr(content, 'timestamp', gmtime())

        if 'source' in content:
            self.url = content.source

        dataEmb: Dict = loads(zstd.decompress(self.metadataEmb))

        self.infoJornada = self.DatosSuministrados['infoJornada']
        self.esPlayoff = self.infoJornada.esPlayOff
        self.jornada = self.infoJornada.jornada
        self.fechaPartido = dataEmb['datosPartido']['fechaHora']
        self.Pabellon = dataEmb['boxscore']['cancha']
        self.Asistencia = dataEmb['boxscore']['asistencia']
        self.Arbitros = dataEmb['boxscore']['arbitros']
        self.ResultadosParciales = dataEmb['resultsParciales']['parciales']
        self.prorrogas = len(self.ResultadosParciales) - 4

        self.procesaDatosEquipos(dataEmb)
        self.procesaPersonas(dataEmb)

    def check(self):
        result = True

        for loc in LocalVisitante:
            if not self.Equipos[loc].get('estads', {}):
                logging.error("Partido: '{}' no se han encontrado estadisticas para {}.")
                result &= False

        return result

    def procesaDatosEquipos(self, dataEmb: Dict):
        for loc in LocalVisitante:
            resEq = {}
            dataEq = dataEmb['boxscore']['equipos'][loc]

            resEq['abrev'] = dataEq['abbreviatedName']
            resEq['id'] = dataEq['clubId']
            resEq['Jugadores'] = dataEq['jugadores']
            resEq['Nombre'] = dataEq['shortName']
            resEq['estads'] = dataEmb['boxscore']['totales'][loc]
            resEq['NoAsignado'] = dataEmb['boxscore']['noAsig'][loc]
            resEq['Puntos'] = resEq['estads']['P']
            resEq['Entrenador'] = dataEq['entrenador']  # TODO: Matchear con ID de entrenador (ya no está en las pags)
            self.Equipos[loc].update(resEq)

        for loc in LocalVisitante:
            self.Equipos[loc]['haGanado']: bool = self.Equipos[loc]['Puntos'] > self.Equipos[OtherLoc(loc)]['Puntos']

        self.VictoriaLocal = self.Equipos['Local']['Puntos'] > self.Equipos['Visitante']['Puntos']

    def procesaPersonas(self, dataEmb: Dict):
        datosComunes = {'competicion': self.competicion, 'temporada': self.temporada, 'jornada': self.jornada}
        for loc in LocalVisitante:
            datosEq = self.Equipos[loc]
            datosRiv = self.Equipos[OtherLoc(loc)]
            datosGlobPart = {
                'equipo': datosEq['Nombre'],
                'CODequipo': datosEq['abrev'],
                'IDequipo': datosEq['id'],
                'rival': datosRiv['Nombre'],
                'CODrival': datosRiv['abrev'],
                'IDrival': datosRiv['id'],
                'url': self.url,
                'haGanado': datosEq['haGanado'],
                'estado': loc,
                'esLocal': loc == "Local",
            }
            for idJug in datosEq['Jugadores']:
                infoJug = dataEmb['boxscore']['infoJugs'][loc][idJug]
                resJug = {
                    'codigo': idJug,
                    'dorsal': infoJug['dorsal'],
                    'esTitular': infoJug['titular'],
                    'nombre': infoJug['nombre'],
                    'esJugador': True,
                    'entrenador': False,
                    'estads': dataEmb['boxscore']['jugadores'][idJug],
                    'haJugado': dataEmb['boxscore']['jugadores'][idJug]['Segs'] > 0,
                    'linkPersona': infoJug['linkPersona']
                }
                resJug.update(datosComunes)
                resJug.update(datosGlobPart)
                self.Jugadores[idJug] = resJug

            resEnt = {
                # 'codigo': No ha parece en los datos embedded de la página
                'nombre': datosEq['Entrenador'],
                'esJugador': False,
                'entrenador': True,
                # 'linkPersona': ya no aparece en los datos
            }
            resEnt.update(datosComunes)
            resEnt.update(datosGlobPart)
            self.Entrenadores[datosEq['Entrenador']] = resEnt

    def jugadoresAdataframe(self) -> pd.DataFrame:
        typesDF = {'competicion': 'object', 'temporada': 'int64', 'jornada': 'int64', 'esLocal': 'bool',
                   'esTitular': 'bool', 'haJugado': 'bool', 'titular': 'category', 'haGanado': 'bool',
                   'enActa': 'bool', }

        dfJugs = [auxJugador2dataframe(typesDF, x, self.fechaPartido) for x in self.Jugadores.values()]
        dfResult = pd.concat(dfJugs, axis=0, ignore_index=True, sort=True).astype(typesDF)
        return dfResult

    def partidoAdataframe(self) -> pd.DataFrame:
        infoCols = ['jornada', 'Pabellon', 'Asistencia', 'prorrogas', 'VictoriaLocal', 'url', 'competicion',
                    'temporada', 'idPartido']
        equipoCols = ['id', 'Nombre', 'abrev']

        infoDict = {k: getattr(self, k) for k in infoCols}
        infoDict['fechaHoraPartido'] = getattr(self, 'fechaPartido')
        infoDict['fechaPartido'] = (infoDict['fechaHoraPartido']).date()

        estadsDict = {loc: {} for loc in self.Equipos}

        for loc in LocalVisitante:
            for col in equipoCols:
                estadsDict[loc][col] = self.Equipos[loc][col]
                other = OtherLoc(loc)
                estadsDict[loc][f"RIV{col}"] = self.Equipos[other][col]

            estadsDict[loc]['local'] = loc == 'Local'
            estadsDict[loc]['haGanado'] = self.DatosSuministrados['equipos'][loc]['haGanado']
            abrev = estadsDict[loc]['RIVabrev']
            estadsDict[loc]['etiqPartido'] = (f"{('v' if estadsDict[loc]['local'] else '@')}{abrev}"
                                              f"{('+' if estadsDict[loc]['haGanado'] else '-')}")
            estadsDict[loc]['convocados'] = len(self.Equipos[loc]['Jugadores'])
            estadsDict[loc]['utilizados'] = len(
                [j for j in self.Equipos[loc]['Jugadores'] if self.Jugadores[j]['haJugado']])

        estadsPart = self.estadsPartido()

        for loc in LocalVisitante:
            estadsDict[loc].update(estadsPart[loc])

        infoDict['Ptot'] = estadsDict['Local']['P'] + estadsDict[OtherLoc('Local')]['P']
        infoDict['Ftot'] = estadsDict['Local']['FP-C'] + estadsDict[OtherLoc('Local')]['FP-C']
        infoDict['POStot'] = estadsDict['Local']['POS'] + estadsDict[OtherLoc('Local')]['POS']

        infoDict['ratio40min'] = 40 / (40 + (infoDict['prorrogas'] * 5))
        infoDict['label'] = "-".join(map(lambda k: estadsDict[k[0]][k[1]], product(LocalVisitante, ['abrev'])))

        estadsDF = pd.DataFrame.from_dict(data=estadsDict, orient='index')

        infoDF = pd.DataFrame.from_dict(data=[infoDict], orient='columns').reset_index(drop=True)
        localDF = estadsDF.loc[estadsDF['local']].reset_index(drop=True)
        visitanteDF = estadsDF.loc[~estadsDF['local']].reset_index(drop=True)

        result = pd.concat([infoDF, localDF, visitanteDF], axis=1, keys=['Info', 'Local', 'Visitante'])
        result.index = result['Info', 'url']
        result.index.name = 'url'
        return result

    def resumenPartido(self):
        jorStr = f"J: {self.jornada:2}"
        if hasattr(self, 'infoJornada'):
            dataJor = self.infoJornada
            if dataJor.esPlayOff:
                jorStr = f"{POLABEL2FASE[dataJor.fasePlayOff.lower()]}({dataJor.partRonda:1})"

        fechaStr = self.fechaPartido.tz_convert(DEFTZ).strftime("%Y-%m-%d %H:%M")

        return (f"{jorStr}: [{fechaStr}] "
                f"{self.EquiposCalendario['Local']['nomblargo']} ({self.CodigosCalendario['Local']}) "
                f"{self.ResultadoCalendario['Local']:d} - {self.ResultadoCalendario['Visitante']:d} "
                f"{self.EquiposCalendario['Visitante']['nomblargo']} ({self.CodigosCalendario['Visitante']})")

    def __str__(self):
        return self.resumenPartido()

    def __getitem__(self, item):
        return getattr(self, item)

    __repr__ = __str__

    def estadsPartido(self):
        result = {loc: {} for loc in LocalVisitante}

        for loc in LocalVisitante:
            result[loc].update(self.Equipos[loc]['estads'])

        for loc in LocalVisitante:
            estads = result[loc]
            other = result[OtherLoc(loc)]
            avanzadas = {}

            avanzadas['Abrev'] = self.Equipos[loc]['abrev']
            avanzadas['Rival'] = self.Equipos[OtherLoc(loc)]['abrev']
            avanzadas['Segs'] = estads['Segs'] / 5

            avanzadas['Prec'] = other['P']

            avanzadas['Ptot'] = estads['P'] + other['P']
            avanzadas['Vict'] = estads['P'] > other['P']
            avanzadas['POS'] = estads['T2-I'] + estads['T3-I'] + (estads['T1-I'] * 0.44) + estads['BP'] - estads['R-O']
            auxOtherPos = other['T2-I'] + other['T3-I'] + (other['T1-I'] * 0.44) + other['BP'] - other['R-O']
            avanzadas['POStot'] = avanzadas['POS'] + auxOtherPos
            avanzadas['OER'] = estads['P'] / avanzadas['POS']
            avanzadas['OERpot'] = estads['P'] / (avanzadas['POS'] - estads['BP'])
            avanzadas['DER'] = other['P'] / auxOtherPos
            avanzadas['DERpot'] = other['P'] / (auxOtherPos - other['BP'])

            # EStadisticas de tiro
            for k in '123':
                kI = f'T{k}-I'
                kC = f'T{k}-C'
                kRes = f'T{k}%'
                avanzadas[kRes] = estads[kC] / estads[kI] * 100.0
            avanzadas['TC-I'] = estads['T2-I'] + estads['T3-I']
            avanzadas['TC-C'] = estads['T2-C'] + estads['T3-C']
            avanzadas['TC%'] = avanzadas['TC-C'] / avanzadas['TC-I'] * 100.0

            avanzadas['t2/tc-I'] = estads['T2-I'] / avanzadas['TC-I'] * 100.0
            avanzadas['t3/tc-I'] = estads['T3-I'] / avanzadas['TC-I'] * 100.0
            avanzadas['t2/tc-C'] = estads['T2-C'] / avanzadas['TC-C'] * 100.0
            avanzadas['t3/tc-C'] = estads['T3-C'] / avanzadas['TC-C'] * 100.0

            avanzadas['PTC'] = auxEqPuntCanastas = estads['T2-C'] * 2 + estads['T3-C'] * 3
            avanzadas['eff-t1'] = estads['T1-C'] * 1 / estads['P'] * 100.0
            avanzadas['eff-t2'] = estads['T2-C'] * 2 / estads['P'] * 100.0
            avanzadas['eff-t3'] = estads['T3-C'] * 3 / estads['P'] * 100.0
            avanzadas['ppTC'] = auxEqPuntCanastas / avanzadas['TC-I']
            avanzadas['PTC/PTCPot'] = auxEqPuntCanastas / (estads['T2-I'] * 2 + estads['T3-I'] * 3) * 100.0

            # Estadisticas de rebote
            avanzadas['EffRebD'] = estads['R-D'] / (estads['R-D'] + other['R-O']) * 100.0
            avanzadas['EffRebO'] = estads['R-O'] / (estads['R-O'] + other['R-D']) * 100.0
            avanzadas['RO/TC-F'] = estads['R-O'] / (avanzadas['TC-I'] - avanzadas['TC-C'])

            # Estadisticas de pase
            avanzadas['A/TC-C'] = estads['A'] / avanzadas['TC-C'] * 100.0
            avanzadas['A/BP'] = estads['A'] / estads['BP']
            avanzadas['A/TC-I'] = estads['A'] / avanzadas['TC-I']
            avanzadas['PNR'] = estads['BP'] - other['BR']

            estads.update(avanzadas)
            result[loc] = estads

        return result

    def descargaEmbMetadata(self, home=None, browser=None, config=None):
        statusMeta = dict.fromkeys(['resumen', 'estadisticas', 'jugadas'], False)
        descargadores = [('resumen', procesaPaginaResumen), ('estadisticas', procesaBoxScore)]
        resultado = {}
        pagsDescargadas = {}

        existURL = None

        for clave, func in descargadores:
            if clave not in self.metadataEnlaces:
                logging.warning("Clave desconocida '%s' en enlaces de partido '%s'", clave, self.url)
                continue

            datos, pagsDescargadas[clave] = func(self.metadataEnlaces[clave], home=home, browser=browser, config=config)
            resultado.update(datos)
            statusMeta[clave] = True

            existURL = self.metadataEnlaces[clave]

        for pag in pagsDescargadas.values():
            auxAvail = procesaMDavailableContent(extraePagDataScripts(pag, 'availableContent'))
            if auxAvail is not None:
                resultado['infoDisponible'] = auxAvail
                break
        if resultado.get('infoDisponible', None) is None:
            logging.warning("Imposible encontrar 'infoDisponible' en partido '%s'", self.url)

        if resultado.get('infoDisponible', {}).get('jugadas', False):
            urlJugadas = mergeURL(existURL, 'jugadas')
            self.metadataEnlaces['jugadas'] = urlJugadas
            resultado['jugadas'], pagsDescargadas['jugadas'] = procesaPlayByPlay(urlJugadas, home=home, browser=browser,
                                                                                 config=config)

        for pag in pagsDescargadas.values():
            completion = []
            if 'resultsParciales' in resultado:
                completion.append(True)
            else:
                auxResParciales = procesaMDresInfoPeriodos(extraePagDataScripts(pag, 'initialMatchHeader'))
                if auxResParciales is not None:
                    resultado['resultsParciales'] = auxResParciales
                    completion.append(True)
                else:
                    completion.append(False)

            if 'datosPartido' in resultado:
                completion.append(True)
            else:
                auxDatosPartido = procesaMDresDatosPartido(extraePagDataScripts(pag, 'initialMatchHeader'))
                if auxDatosPartido is not None:
                    resultado['datosPartido'] = auxDatosPartido
                    completion.append(True)
                else:
                    completion.append(False)

            if all(completion):
                break

        self.metadataEmb = zstd.compress(dumps(resultado))


def auxJugador2dataframe(typesDF, jugador, fechaPartido):
    dictJugador = {}
    dictJugador['enActa'] = True
    dictJugador['acta'] = 'S'

    # Añade las estadísticas al resultado saltándose ciertas columnas no relevantes
    for dato in jugador:
        if dato in ['esJugador', 'entrenador', 'estads', 'estado']:
            continue
        dictJugador[dato] = jugador[dato]

    if jugador['haJugado']:
        # Añade campos sacados de la página ACB
        for dato in jugador['estads']:
            dictJugador[dato] = jugador['estads'][dato]
            typesDF[dato] = 'float64'

        # Añade campos derivados
        dictJugador['TC-I'] = dictJugador['T2-I'] + dictJugador['T3-I']
        dictJugador['TC-C'] = dictJugador['T2-C'] + dictJugador['T3-C']
        dictJugador['PTC'] = 2 * dictJugador['T2-C'] + 3 * dictJugador['T3-C']
        dictJugador['ppTC'] = dictJugador['PTC'] / dictJugador['TC-I'] if dictJugador['TC-I'] else np.nan
        dictJugador['A/BP'] = dictJugador['A'] / dictJugador['BP'] if dictJugador['BP'] else np.nan
        dictJugador['A/TC-I'] = dictJugador['A'] / dictJugador['TC-I'] if dictJugador['TC-I'] else np.nan

        typesDF['ppTC'] = 'float64'
        typesDF['PTC'] = 'float64'
        typesDF['A/BP'] = 'float64'
        typesDF['A/TC-I'] = 'float64'

        for k in '123C':
            kI = f'T{k}-I'
            kC = f'T{k}-C'
            kRes = f'T{k}%'
            dictJugador[kRes] = (dictJugador[kC] / dictJugador[kI] * 100.0) if dictJugador[kI] else np.nan
            typesDF[kI] = 'float64'
            typesDF[kC] = 'float64'
            typesDF[kRes] = 'float64'

    else:
        dictJugador['V'] = 0.0
        typesDF['V'] = 'float64'

    dfresult = pd.DataFrame.from_dict(dictJugador, orient='index').transpose()
    dfresult['fechaPartido'] = fechaPartido
    dfresult['local'] = dfresult['esLocal'].map(local2esp)
    dfresult['titular'] = dfresult['esTitular'].map(titular2esp)

    dfresult['resultado'] = dfresult['haGanado'].map(haGanado2esp)
    dfresult['jugado'] = dfresult['haJugado'].map(bool2esp)

    return dfresult


def procesaPaginaResumen(urlResumen: Union[str, DownloadedPage], home=None, browser=None,
                         config=None) -> Tuple[dict, DownloadedPage]:
    if isinstance(urlResumen, DownloadedPage):
        resumenPage = urlResumen
    else:
        browser, config = prepareDownloading(browser, config)
        resumenPage = downloadPage(urlResumen, home=home, browser=browser, config=config)

    resultado = {'comparativaEstads': procesaMDresEstadsCompar(
        extraePagDataScripts(resumenPage, 'initialMatchStatsComparative')),
        'infoRachas': procesaMDresInfoRachas(extraePagDataScripts(resumenPage, 'initialLeadTracker')),
        'cartaTiro': procesaMDresCartaTiro(extraePagDataScripts(resumenPage, 'initialShotmap')), }

    return resultado, resumenPage


def procesaPlayByPlay(urlJugadas: Union[str, DownloadedPage], home=None, browser=None,
                      config=None) -> Tuple[dict, DownloadedPage]:
    if isinstance(urlJugadas, DownloadedPage):
        jugadasPage = urlJugadas
    else:
        browser, config = prepareDownloading(browser, config)
        jugadasPage = downloadPage(urlJugadas, home=home, browser=browser, config=config)

    auxResult = procesaMDjugadas(extraePagDataScripts(jugadasPage, 'initialMatchPlayByPlay'))

    if len(auxResult['clavesDesconocidas']) > 0:
        logging.warning("Jugadas desconocidas en partido '%s'", urlJugadas)
        for jugKey, listaJugDescon in auxResult['clavesDesconocidas'].items():
            logging.warning("Jugada no traducida: %s [%i]", jugKey, len(listaJugDescon))
            for play in sorted(listaJugDescon, key=jugadaSort, reverse=True):
                logging.warning(jugada2str(play))

    logging.debug("Resumen de jugadas en partido")
    for k in sorted(auxResult['contadores'].keys(), key=jugadaKey2sort):
        v = auxResult['contadores'][k]
        logging.debug("%s [%s]: %s", jugadaKey2str(k), f"{v:3}", jugadaTag2Desc.get(k, ""))

    logging.debug("Estado parseo Trad:%s No trad: %s ", auxResult['contConocidas'][True],
                  auxResult['contConocidas'][False])

    resultado = {'playByPlay': auxResult['jugadas'], }
    return resultado, jugadasPage


def procesaBoxScore(urlBoxscore: Union[str, DownloadedPage], home=None, browser=None,
                    config=None) -> Tuple[dict, DownloadedPage]:
    if isinstance(urlBoxscore, DownloadedPage):
        boxscorePage = urlBoxscore
    else:
        browser, config = prepareDownloading(browser, config)
        boxscorePage: DownloadedPage = downloadPage(urlBoxscore, home=home, browser=browser, config=config)

    linksJugs = extraeLinksPersonasPtBSc(boxscorePage, urlBase=boxscorePage.source)
    resultado = {
        'boxscore': procesaMDboxscore(extraePagDataScripts(boxscorePage, 'initialStatistics'), linksPers=linksJugs), }

    return resultado, boxscorePage


def extraeLinksPersonasPtBSc(pag: DownloadedPage, urlBase: str = URL_BASE) -> Dict[str, str]:
    result = {}

    reTablaBsc = re.compile(r'MatchTeamStatisticsTable_matchTeamStatisticsTable__table__.*_')
    tablaBsc: Tag
    for tablaBsc in pag.data.find_all('table', {'class': reTablaBsc}):
        for a in tablaBsc.find_all('a'):
            destURL = mergeURL(urlBase, a['href'])
            idPers = getIDfromEncURL(destURL)

            result[idPers] = destURL

    if len(result) == 0:
        raise ValueError(f"extraeLinksPersonasPtBSc: no se han encontrado enlaces en '{pag.source}'")

    return result

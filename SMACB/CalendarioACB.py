import ast
import logging
import re
import sys
import traceback
from collections import defaultdict
from copy import copy
from time import gmtime
from typing import Set, Optional, Dict, Any
from urllib.parse import urlparse, urlunparse, parse_qs, ParseResult, urlencode

import bs4.element
import json5
import pandas as pd
from CAPcore.Misc import listize, onlySetElement
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage

from Utils.FechaHora import NEVER, PATRONFECHA, PATRONFECHAHORA, fecha2fechaCalDif, procesaFechaJornada
from Utils.Web import prepareDownloading, tagAttrHasValue, generaURLEstadsPartido
from .Constants import URL_BASE, REGEX_JLR, REGEX_PLAYOFF, numPartidoPO2jornada, infoJornada, LocalVisitante, OtherLoc

logger = logging.getLogger()

calendario_URLBASE = 'https://www.acb.com/es/calendario'

# https://www.acb.com/calendario/index/temporada_id/2018
# https://www.acb.com/calendario/index/temporada_id/2019/edicion_id/952
template_CALENDARIOYEAR = "https://www.acb.com/calendario/index/temporada_id/{year}"
template_PARTIDOSEQUIPO = "https://www.acb.com/club/partidos/id/{idequipo}"

ETIQubiq = ['local', 'visitante']

embeddedDataTemporadas: Optional[dict] = None
embeddedDataEquipos: Optional[dict] = None
embeddedDataCalendario: Optional[dict] = None

UMBRALbusquedaDistancia = 1  # La comparación debe ser >

CALENDARIOEQUIPOS = {}
JORNADASCOMPLETAS: Optional[Set] = None


class CalendarioACB:

    def __init__(self, urlbase=calendario_URLBASE, **kwargs):
        self.timestamp = gmtime()
        self.competicion = kwargs.get('competicion', "LACB")
        self.nombresCompeticion = defaultdict(int)
        self.edicion = kwargs.get('edicion')
        self.Partidos = {}
        self.Jornadas = {}
        self.tradEquipos = {'n2c': defaultdict(set), 'c2n': defaultdict(set), 'n2i': defaultdict(set),
                            'i2n': defaultdict(set), 'c2i': defaultdict(set), 'i2c': defaultdict(set)}
        self.urlbase = urlbase
        self.url = None

    def actualizaCalendario(self, home=None, browser=None, config=None):
        browser, config = prepareDownloading(browser, config)
        calendarioPage: DownloadedPage = self.descargaCalendario(home=home, browser=browser, config=config)

        self.procesaCalendario(calendarioPage, home=self.url, browser=browser, config=config)

    def procesaCalendario(self, content: DownloadedPage, **kwargs):
        if 'timestamp' in content:
            self.timestamp = content.timestamp
        if 'source' in content:
            self.url = content.source
        calendarioData: bs4.element.Tag = content.data

        reRound = re.compile(r"^Round_round___")
        reRoundTitle = re.compile(r"^RoundTitle_roundTitle__")
        jornadasCurrCal = set()

        for divJ in calendarioData.find_all("div", {"class": reRound}):  # ,
            datosCab = procesaCab(divJ.find("div", {'class': reRoundTitle}))
            if datosCab is None:
                continue

            self.Jornadas[datosCab['jornada']] = self.procesaBloqueJornada(divJ, datosCab, **kwargs)
            jornadasCurrCal.add(datosCab['jornada'])

        jor2del: set = set(self.Jornadas.keys()).difference(jornadasCurrCal)
        for j in jor2del:
            print(f"Eliminando jornada desaparecida '{j}'")
            self.Jornadas.pop(j)

    def esJornadaPlayOff(self, currJ: int):
        return (len(self.Jornadas[currJ]['partidos']) + len(self.Jornadas[currJ]['pendientes'])) != (
                len(self.tradEquipos['c2n']) // 2)

    def actualizaDatosPlayoffJornada(self):
        # Calcula datos seguros a partir de los partidos/jornadas
        for jNum, jData in self.Jornadas.items():
            if jData['esPlayoff'] is None:
                jData['esPlayoff'] = self.esJornadaPlayOff(jNum)

            if 'idEmparej' not in jData:
                jData['idEmparej'] = set()
            if 'numPartidos' not in jData:
                jData['numPartidos'] = len(jData['partidos']) + len(jData['pendientes'])

            if len(jData.get('idEmparej', {})) == 0:
                for game in jData['partidos'] + jData['pendientes']:
                    if 'claveEmparejamiento' not in game:
                        game['claveEmparejamiento'] = self.idGrupoEquiposNorm(game['participantes'])
                        jData['equipos'].update(game['participantes'])
                        jData['idEmparej'].add(game['claveEmparejamiento'])

    def nuevaTraduccionEquipo2Codigo(self, nombres, abrev, idEq=None):
        result = False
        eqList = listize(nombres)

        for eqName in eqList:
            if (eqName not in self.tradEquipos['n2c']) or (abrev not in self.tradEquipos['c2n']):
                result = True
            self.tradEquipos['n2c'][eqName].add(abrev)
            (self.tradEquipos['c2n'][abrev]).add(eqName)

            if idEq is not None:
                if (idEq not in self.tradEquipos['i2c']) or (idEq not in self.tradEquipos['i2n']) or (
                        eqName not in self.tradEquipos['n2i']) or (abrev not in self.tradEquipos['c2i']):
                    result = True
                self.tradEquipos['i2c'][idEq].add(abrev)
                (self.tradEquipos['c2i'][abrev]).add(idEq)
                self.tradEquipos['n2i'][eqName].add(idEq)
                (self.tradEquipos['i2n'][idEq]).add(eqName)

        return result

    def descargaCalendario(self, home=None, browser=None, config=None) -> DownloadedPage:
        browser, config = prepareDownloading(browser, config)

        global embeddedDataTemporadas  # pylint: disable=global-statement
        global embeddedDataEquipos  # pylint: disable=global-statement
        global embeddedDataCalendario  # pylint: disable=global-statement

        if self.url is None:
            logger.info("DescargaCalendario. Creando URL %s. Edicion: %s. Compo: %s", self.url, self.edicion,
                        self.competicion)
            pagCalendario = downloadPage(self.urlbase, home=home, browser=browser, config=config)

            avFilters = extractPagDataScripts(pagCalendario, 'availableFilters')
            embeddedDataTemporadas = procesaMDfl2calendarIDs(avFilters)

            currYear = embeddedDataTemporadas['currFilters']['seaYear']
            currComp = embeddedDataTemporadas['currFilters']['compKey']

            if self.edicion is None:
                self.edicion = currYear

            self.url = composeURLcalendario(self.urlbase, targComp=self.competicion, targTemp=self.edicion)
            if (self.edicion == currYear) and (self.competicion == currComp):
                embeddedDataEquipos = procesaMDteams2InfoEqs(avFilters)
                embeddedDataCalendario = processMDfl2InfoCal(avFilters)
                for embData in embeddedDataEquipos['eqData'].values():
                    self.nuevaTraduccionEquipo2Codigo([embData['nomblargo'], embData['nombcorto']], embData['abrev'],
                                                      embData['id'])
                return pagCalendario

            logger.info("DescargaCalendario. URL %s", self.url)
            result = downloadPage(self.url, browser=browser, home=None, config=config)

        else:
            logger.info("DescargaCalendario. URL %s", self.url)
            result = downloadPage(self.url, browser=browser, home=None, config=config)

        avFilters = extractPagDataScripts(result, 'availableFilters')
        embeddedDataTemporadas = procesaMDfl2calendarIDs(avFilters)
        embeddedDataEquipos = procesaMDteams2InfoEqs(avFilters)
        embeddedDataCalendario = processMDfl2InfoCal(avFilters)

        for embData in embeddedDataEquipos['eqData'].values():
            self.nuevaTraduccionEquipo2Codigo([embData['nomblargo'], embData['nombcorto']], embData['abrev'],
                                              embData['id'])

        return result

    def procesaBloqueJornada(self, divDatos: bs4.element.Tag, dictCab: dict, **kwargs):
        # TODO: incluir datos de competicion
        result = {}
        result['nombre'] = self.competicion
        result['jornada'] = dictCab['jornada']
        result['fechas'] = set()
        result['partidos'] = []
        result['pendientes'] = []
        result['equipos'] = set()
        result['idEmparej'] = set()
        result['esPlayoff']: bool = dictCab['esPlayoff']
        result['infoJornada']: infoJornada = dictCab['infoJornada']

        # print(divDatos.prettify())
        for bloqueFecha in divDatos.find_all("h3"):
            fechaParts = procesaFechaJornada(bloqueFecha.getText())
            auxDictCab = {'fechaParts': fechaParts}
            auxDictCab.update(dictCab)
            for artP in bloqueFecha.find_next_siblings('div'):
                datosPart = self.procesaBloquePartido(auxDictCab, artP)
                datosPart['infoJornada']: infoJornada = result['infoJornada']

                result['equipos'].update(datosPart['participantes'])
                result['idEmparej'].add(datosPart['claveEmparejamiento'])

                if datosPart['pendiente']:
                    if datosPart['fechaPartido'] == NEVER:
                        nuevaFecha = self.recuperaFechaAmbigua(datosPart, **kwargs)
                        if nuevaFecha:
                            datosPart['fechaPartido'] = nuevaFecha
                    result['pendientes'].append(datosPart)
                else:
                    self.Partidos[datosPart['url']] = datosPart
                    result['partidos'].append(datosPart)

        result['numPartidos'] = len(result['partidos']) + len(result['pendientes'])
        return result

    def procesaBloquePartido(self, datosJornada: dict, divPartido: bs4.element.Tag):
        # TODO: incluir datos de competicion
        resultado = {}
        resultado['pendiente'] = True
        resultado['fechaPartido'] = datosJornada.get('fechaParts', NEVER)
        resultado['jornada'] = datosJornada['jornada']

        resultado['cod_competicion'] = self.competicion
        resultado['cod_edicion'] = self.edicion

        reHoraPart = re.compile('^RoundMatch_roundMatch__time__')
        divHoraPart = divPartido.find('div', {'class': reHoraPart})

        if divHoraPart and not isSkeleton(divHoraPart):
            try:
                resultado[('fechaPartido')] = pd.to_datetime(divHoraPart.getText())
            except Exception as exc:
                print(exc)
                print(f"Problems parsing date '{divHoraPart.getText()}'  ", sys.exc_info())
                traceback.print_tb(sys.exc_info()[2])
                resultado['fechaPartido'] = datosJornada['fechaParts']

        reDatosEquiposPartido = re.compile(r"^RoundMatch_roundMatch__teams__")
        auxDatosEqs = divPartido.find('div', {'class': reDatosEquiposPartido})
        if not auxDatosEqs:
            raise ValueError(f"Partido sin equipos!\n{divPartido.prettify()}")

        datosPartEqs = procesaDatosEquiposPartido(auxDatosEqs)
        resultado['equipos'] = datosPartEqs
        resultado['loc2abrev'] = {loc: datosPartEqs[loc]['abrev'] for loc in LocalVisitante}
        resultado['abrev2loc'] = {datosPartEqs[loc]['abrev']: loc for loc in LocalVisitante}
        resultado['participantes'] = {datosPartEqs[loc]['abrev'] for loc in LocalVisitante}
        resultado['claveEmparejamiento'] = self.idGrupoEquiposNorm(resultado['participantes'])

        datosMD = embeddedDataCalendario[resultado['jornada']]['partidos'][resultado['claveEmparejamiento']]
        CAMPOSAMOVER = ['fechaPartido', 'partido']
        resultado.update({k: datosMD[k] for k in CAMPOSAMOVER if k in datosMD})

        if all('puntos' in eq for eq in datosPartEqs.values()):
            resultado['pendiente'] = False
            resultado['resultado'] = {loc: datosPartEqs[loc]['puntos'] for loc in LocalVisitante}
            resultado['url'] = generaURLEstadsPartido(resultado['partido'], urlRef=self.url)

        return resultado

    def recuperaFechaAmbigua(self, infoPart, **kwargs):
        result = None

        for abrev in infoPart['participantes']:
            idEquipo = self.tradEquipos['c2i'].get(abrev, None)
            if idEquipo:  # Necesitamos el ID para descargar partidos. El id se aprende a partir de pags de resultados
                valID = copy(idEquipo).pop()
                calendarioEquipo = recuperaPartidosEquipo(valID, **kwargs)
                if calendarioEquipo:
                    CALENDARIOEQUIPOS[valID] = calendarioEquipo
                    result = calendarioEquipo['jornadas'].get(infoPart['jornada'], None)
                    return result

        return result

    def partidosEquipo(self, abrEq):
        targAbrevs = self.abrevsEquipo(abrEq)

        jugados = [p for p in self.Partidos.values() if
                   targAbrevs.intersection(p['participantes']) and not p['pendiente']]
        pendientes = []
        for dataJor in self.Jornadas.values():
            auxPendientes = [p for p in dataJor['pendientes'] if
                             targAbrevs.intersection(p['participantes']) and p['pendiente']]
            pendientes.extend(auxPendientes)
        for p in jugados:
            for _, e in p['equipos'].items():
                if 'idEq' not in e:
                    e['idEq'] = onlySetElement(self.tradEquipos['c2i'][e['abrev']])
        for p in pendientes:
            for _, e in p['equipos'].items():
                if 'idEq' not in e:
                    e['idEq'] = onlySetElement(self.tradEquipos['c2i'][e['abrev']])

        return jugados, pendientes

    def abrevsEquipo(self, abrEq):
        if abrEq not in self.tradEquipos['c2n']:
            trad2str = " - ".join(
                [f"'{k}': {','.join(sorted(self.tradEquipos['c2n'][k]))}" for k in sorted(self.tradEquipos['c2n'])])
            raise KeyError(f"partidosEquipo: abreviatura pedida '{abrEq}' no existe: {trad2str}")

        # Consigue las abreviaturas para el equipo
        targAbrevs = set()
        iAbrev = self.tradEquipos['c2i'][abrEq]
        for i in iAbrev:
            targAbrevs.update(self.tradEquipos['i2c'][i])

        return targAbrevs

    def idGrupoEquiposNorm(self, conjAbrevs):
        result = ",".join(map(str, sorted([str(onlySetElement(self.tradEquipos['c2i'][e])) for e in conjAbrevs])))
        return result

    def jornadasCompletas(self):
        """
        Devuelve las IDs de jornadas para las que se han jugado todos los partidos
        :return: set con las jornadas para las que no quedan partidos (el id, entero)
        """
        # pylint: disable=global-statement
        global JORNADASCOMPLETAS
        # pylint: enable=global-statement

        if JORNADASCOMPLETAS is not None:
            return JORNADASCOMPLETAS

        result = {j for j, data in self.Jornadas.items() if len(data['pendientes']) == 0}
        JORNADASCOMPLETAS = result
        return result

    def cal2dict(self):

        result = {'pendientes': {}, 'jugados': {}}
        for data in self.Jornadas.values():
            for pend in data['pendientes']:
                pendK = p2DictK(self, pend)
                if pendK:
                    result['pendientes'][pendK] = fecha2fechaCalDif(pend['fechaPartido'])
            for jug in data['partidos']:
                pendK = p2DictK(self, jug)
                if pendK:
                    result['jugados'][pendK] = jug['url']

        return result


def BuscaCalendario(url=URL_BASE, home=None, browser=None, config=None):
    if config is None:
        config = {}
    indexPage = downloadPage(url, home, browser, config)

    index = indexPage.data

    callinks = index.find_all("a", text="Calendario")

    if len(callinks) == 1:
        link = callinks[0]
    else:
        for auxlink in callinks:
            if 'calendario.php' in auxlink['href']:
                link = auxlink
                break
        else:
            raise SystemError(f"Too many or none links to Calendario. {callinks}")

    result = mergeURL(url, link['href'])

    return result


def compo2clave(listaCompos):
    """
    Dado un diccionario con lo que aparece en el desplegable (idComp -> nombre compo), devuelve otro con las claves
    tradicionales (pre verano 2019)
    :param listaCompos:
    :return:
    """
    PATliga = r'^liga\W'
    PATsupercopa = r'^supercopa\W'
    PATcopa = r'^copa\W.*rey'

    result = {}

    for idComp, label in listaCompos.items():
        if re.match(PATliga, label, re.IGNORECASE):
            result['LACB'] = idComp
        elif re.match(PATsupercopa, label, re.IGNORECASE):
            result['SCOPA'] = idComp
        elif re.match(PATcopa, label, re.IGNORECASE):
            result['COPA'] = idComp

    return result


def isSkeleton(tagElem: bs4.element.Tag, tag2search: str = "span") -> bool:
    if tagElem is None:
        return True
    reSkel = re.compile(r"^_skeleton_")
    if tagElem.find(tag2search, {"class": reSkel}):
        return True
    return False


def procesaCab(cab: bs4.element.Tag) -> Optional[Dict]:
    """
    Extrae datos relevantes de la cabecera de cada jornada en el calendario
    :param cab: div que contiene la cabecera COMPLETA
    :return:  {'comp': 'Liga Endesa', 'yini': '2018', 'yfin': '2019', 'jor': '46'}
    """
    if isSkeleton(cab):
        return None
    nombreJornada = cab.getText()

    resultado = {}

    reJLR = re.match(REGEX_JLR, nombreJornada, re.IGNORECASE)

    if reJLR:
        resultado['jornada'] = int(reJLR.group('jornada'))
        resultado['esPlayoff'] = False
        resultado['infoJornada'] = infoJornada(jornada=resultado['jornada'], esPlayOff=False)
    else:
        resultado['esPlayoff'] = True
        rePoff = re.match(REGEX_PLAYOFF, nombreJornada, re.IGNORECASE)

        if rePoff is None:
            raise ValueError(f"procesaCab: {cab.prettify()}: texto '{nombreJornada}' no casa RE '{REGEX_PLAYOFF}'")

        etiqPOff = rePoff.group('etiqFasePOff')
        numPartPOff = rePoff.group('numPartPoff')
        resultado['jornada'] = numPartidoPO2jornada(etiqPOff, numPartPOff)
        resultado['infoJornada'] = infoJornada(jornada=resultado['jornada'], esPlayOff=resultado['esPlayoff'],
                                               fasePlayOff=etiqPOff.lower(),
                                               partRonda=int(numPartPOff))

    return resultado


def recuperaPartidosEquipo(idEquipo, home=None, browser=None, config=None):
    if idEquipo in CALENDARIOEQUIPOS:
        return CALENDARIOEQUIPOS[idEquipo]

    urlDest = template_PARTIDOSEQUIPO.format(idequipo=idEquipo)

    browser, config = prepareDownloading(browser, config)
    partidosPage = downloadPage(dest=urlDest, home=home, browser=browser, config=config)

    if partidosPage is None:
        return None

    dataPartidos = procesaPaginaPartidosEquipo(partidosPage)
    return dataPartidos


def procesaPaginaPartidosEquipo(content: DownloadedPage):
    result = {}
    result['jornadas'] = {}

    if 'timestamp' in content:
        result['timestamp'] = content.timestamp
    if 'source' in content:
        result['source'] = content.source

    result['data'] = content.data

    pagData = result['data']

    divTabla = pagData.find('div', {'class': 'todos_los_partidos'})

    if divTabla is None:
        return None

    for fila in divTabla.findAll('tr'):
        auxJornada = fila.find('td', {'class': 'jornada'})

        if auxJornada is None:
            continue

        auxFecha = fila.find('td', {'class': 'fecha'}).get_text()
        auxHora = fila.find('td', {'class': 'vod'}).get_text()

        cadJornada = auxJornada.get_text()
        if cadJornada is None:
            return None

        jornada = cadJornada.strip()
        cadFechaFin = auxFecha.strip()
        cadHora = auxHora.strip() if auxHora else None

        if cadFechaFin:
            formato = PATRONFECHAHORA if cadHora else PATRONFECHA
            cadMezclada = f"{cadFechaFin} {cadHora.strip()}" if cadHora else cadFechaFin
            try:
                fechaPart = pd.to_datetime(cadMezclada, format=formato)
            except ValueError:
                print(f"procesaPaginaPartidosEquipo: '{cadMezclada}' no casa RE '{fila}'")
                return None
        else:
            fechaPart = NEVER

        result['jornadas'][jornada] = fechaPart

    return result


def p2DictK(cal: CalendarioACB, datosPart: dict) -> str:
    jor = f"{datosPart['jornada']}"
    idLoc = onlySetElement(cal.tradEquipos['c2i'][datosPart['loc2abrev']['Local']])
    idVis = onlySetElement(cal.tradEquipos['c2i'][datosPart['loc2abrev']['Visitante']])
    result = "#".join((jor, idLoc, idVis)) if (isinstance(idLoc, str) and isinstance(idVis, str)) else None
    return result


def dictK2partStr(cal: CalendarioACB, partK: str) -> str:
    jor, idLoc, idVis = partK.split('#')
    abrLoc = list(cal.tradEquipos['i2c'][idLoc])[-1]
    abrVis = list(cal.tradEquipos['i2c'][idVis])[-1]

    result = f"J{int(jor):02}: {abrLoc}-{abrVis}"
    return result


def extractPagDataScripts(calPage: DownloadedPage, keyword=None):
    patWrapper = r'^self\.__next_f\.push\((.*)\)$'

    calData = calPage.data

    result = []

    for scr in calData.find_all('script'):
        scrText = scr.text
        if keyword and keyword not in scrText:
            continue
        reWrapper = re.match(patWrapper, scrText)
        if reWrapper is None:
            continue

        wrappedText = reWrapper.group(1)

        try:
            firstEval = ast.literal_eval(wrappedText)
        except SyntaxError:
            logging.exception("No scanea Eval: %s", scr.prettify())
            continue

        patForcedict = r"^\s*([^:]+)\s*:\s*(.*)\s*$"
        reForceDict = re.match(patForcedict, firstEval[1])

        if reForceDict is None:
            logger.error("No casa RE '%s' : %s", reForceDict, scr.prettify())
            continue
        dictForced = "{" + f'"{reForceDict.group(1)}":{reForceDict.group(2)}' + "}"
        try:
            jsonParsed = json5.loads(dictForced)
        except Exception:
            logging.exception("No scanea json: %s", scr.prettify())
            continue

        result.append(jsonParsed)

    return result if len(result) > 1 else result[0]


def procesaMDfl2calendarIDs(rawData: dict) -> Dict[str, Dict]:
    result = {'compKey2compId': {}, 'compId2compKey': {}, 'seaId2seaYear': {}, 'seaYear2seaId': {}, 'seaData': {},
              'currFilters': {}}

    # pp(rawData)
    auxFilterData: dict = list(rawData.values())[0][3]['data']

    filterAv = auxFilterData['availableFilters']

    name2comp = {'Liga Nacional': 'LACB', 'Copa de España': 'COPA', 'Supercopa': 'SCOPA'}
    for v in filterAv['competitions']:
        cName = v['name']
        cId = str(v['id'])
        if cName not in name2comp:
            continue
        result['compKey2compId'][name2comp[cName]] = cId
        result['compId2compKey'][cId] = name2comp[cName]

    s: dict
    for s in filterAv['seasons']:
        sId = str(s['id'])
        sYear = str(s['startYear'])
        result['seaId2seaYear'][sId] = sYear
        result['seaYear2seaId'][sYear] = sId
        result['seaData'][sYear] = s

    auxCurrData = auxFilterData['selectedFilters']
    result['currFilters'].update(auxCurrData)
    result['currFilters']['seaYear'] = result['seaId2seaYear'][str(auxCurrData['season'])]
    result['currFilters']['compKey'] = result['compId2compKey'][str(auxCurrData['competition'])]
    result['currFilters']['seaId'] = str(auxCurrData['season'])
    result['currFilters']['compId'] = str(auxCurrData['competition'])

    return result


def procesaMDteams2InfoEqs(rawData: dict) -> Dict[str, Dict]:
    result = {'eqData': {}, 'eqAbrev2eqId': {}, 'seq2eqId': {}, 'seq2eqAbrev': {}, 'eqId2eqAbrev': {}}

    eqDataTxlat = {'id': 'calId', 'clubId': 'id', 'fullName': 'nomblargo', 'shortName': 'nombcorto',
                   'abbreviatedName': 'abrev',
                   'logo': 'icono', 'secondaryLogo': 'iconoSec'}
    auxFilterData: dict = list(rawData.values())[0][3]['data']

    auxTeamsData: dict = auxFilterData['teams']

    for seq, eq in enumerate(auxTeamsData):
        eqAbrev = eq['abbreviatedName']
        eqId = str(eq['clubId'])
        result['seq2eqId'][str(seq)] = eqId
        result['seq2eqAbrev'][str(seq)] = eqAbrev
        result['eqAbrev2eqId'][eqAbrev] = eqId
        result['eqId2eqAbrev'][eqId] = eqAbrev
        result['eqData'][eqId] = {eqDataTxlat.get(k, k): v for k, v in eq.items()}

    return result


def processMDfl2InfoCal(rawData: dict) -> Dict[str, Dict]:
    """
    Saca la información de calendario del script que lleva embebida la página del calendario
    :param rawData:
    :return:
    """
    global embeddedDataEquipos  # pylint: disable=global-statement

    if embeddedDataCalendario is not None:
        return embeddedDataCalendario

    result = {}

    LV2HA = {'Local': 'home', 'Visitante': 'away'}

    if embeddedDataEquipos is None:
        embeddedDataEquipos = procesaMDteams2InfoEqs(rawData)

    auxFilterData: dict = list(rawData.values())[0][3]['data']
    auxRounds: dict = auxFilterData['rounds']

    for r in auxRounds:
        infoRound = {'partidos': {}, 'pendientes': set(), 'jugados': set(), 'equipos': set(), 'idEmparej': set()}

        infoRound.update(MDround2roundData(r))

        for g in r['matches']:
            partPendiente: bool = g['matchStatus'] != 'FINALIZED'
            datosPart = {'fechaPartido': pd.to_datetime(g['startDateTime']),
                         'pendiente': partPendiente, 'equipos': {}, 'resultado': {}}
            datosPart['partido'] = g['id']

            for loc in LocalVisitante:
                datosEq = {}
                clavTrad = LV2HA[loc]
                clavTradOther = LV2HA[OtherLoc(loc)]

                eqSeq = g[clavTrad + 'Team'].split(':')[-1]
                datosEq['id'] = embeddedDataEquipos['seq2eqId'][eqSeq]
                datosEq.update(embeddedDataEquipos['eqData'][datosEq['id']])
                if not partPendiente:
                    datosEq['puntos'] = g[clavTrad + 'TeamScore']
                    datosEq['haGanado'] = datosEq['puntos'] > g[clavTradOther + 'TeamScore']
                    datosPart['resultado'][loc] = datosEq['puntos']
                    infoRound['equipos'].add(datosEq['abrev'])
                datosPart['equipos'][loc] = datosEq

            datosPart['loc2abrev'] = {k: v['abrev'] for k, v in datosPart['equipos'].items()}
            datosPart['abrev2loc'] = {v['abrev']: k for k, v in datosPart['equipos'].items()}
            datosPart['participantes'] = {v['abrev'] for v in datosPart['equipos'].values()}
            datosPart['claveEmparejamiento'] = ",".join(sorted([str(v['id']) for v in datosPart['equipos'].values()]))

            infoRound['idEmparej'].add(datosPart['claveEmparejamiento'])

            infoRound['partidos'][datosPart['claveEmparejamiento']] = datosPart
            if partPendiente:
                infoRound['pendientes'].add(datosPart['claveEmparejamiento'])
            else:
                infoRound['jugados'].add(datosPart['claveEmparejamiento'])

        result[infoRound['jornada']] = infoRound

    return result


def getCalendario2025format(url=calendario_URLBASE, home=None, browser=None, config=None):
    result = {}

    if config is None:
        config = {}
    calPage = downloadPage(url, home, browser, config)

    auxDataCal: Dict[str, list] = extractPagDataScripts(calPage, 'availableFilters')

    result.update(procesaMDfl2calendarIDs(auxDataCal))
    result.update(procesaMDteams2InfoEqs(auxDataCal))

    return result


def composeURLcalendario(currURL: str = calendario_URLBASE, targComp: str = None, targTemp=None,
                         ) -> str:
    if embeddedDataTemporadas is None:
        raise ValueError("composeURLcalendario: necesito informacion para filtros")

    if targTemp is None:
        targTemp = embeddedDataTemporadas['currFilters']['seaYear']
    if targComp is None:
        targComp = embeddedDataTemporadas['currFilters']['compKey']

    compsCurr: ParseResult = urlparse(currURL)
    infoParams = parse_qs(compsCurr.query)
    desiredParams = copy(infoParams)
    desiredParams.update({'temporada': embeddedDataTemporadas['seaData'][targTemp]['id'],
                          'competicion': embeddedDataTemporadas['compKey2compId'][targComp]})
    result = urlunparse(
        ParseResult(scheme=compsCurr.scheme, netloc=compsCurr.netloc, path=compsCurr.path, params=compsCurr.params,
                    query=urlencode(desiredParams), fragment=compsCurr.fragment))

    return result


reDatosEq = re.compile(r'^RoundMatch_roundMatch__(home|away)Team__')
reDatosEqLink = re.compile(r'^RoundMatch_roundMatch__teamLink___')
reDatosEqLinkLogo = re.compile(r'^RoundMatch_roundMatch__teamLogoLink__')

reDatosEqLinkName = re.compile(r'^RoundMatch_roundMatch__teamName--fullName__')
reDatosEqLinkAbrev = re.compile(r'^RoundMatch_roundMatch__teamName--shortName__')
reDatosEqPScore = re.compile(r'^RoundMatch_roundMatch__teamScore__')

CAMPOSDEEQUIPOAMOVER = ['nombcorto', 'id']


def procesaDatosEquiposPartido(divData: bs4.element.Tag) -> dict:
    result = {}

    for loc, divEq in zip(LocalVisitante, divData.find_all('div', {'class': reDatosEq})):
        datosEq = procesaDivsUnicoEquipo(divData, divEq)

        result[loc] = datosEq

    if all('puntos' in result[loc] for loc in LocalVisitante):
        for loc in LocalVisitante:
            result[loc]['haGanado'] = result[loc]['puntos'] > result[OtherLoc(loc)]['puntos']
            result[loc]['pendiente'] = False
    else:
        for loc in LocalVisitante:
            result[loc]['pendiente'] = True

    return result


def procesaDivsUnicoEquipo(divData: bs4.Tag, divEq: bs4.Tag) -> dict[Any, Any]:
    datosEq = {}

    for linkTeam in divEq.find_all('a', {'class': reDatosEqLink}):
        if tagAttrHasValue(linkTeam, 'class', reDatosEqLinkLogo):
            continue

        datosEq['hrefTeam'] = linkTeam['href']
        divTeamName = linkTeam.find('span', {'class': reDatosEqLinkName})
        if divTeamName:
            datosEq['nomblargo'] = divTeamName.getText().strip()
        divTeamAbrev = linkTeam.find('span', {'class': reDatosEqLinkAbrev})
        if divTeamAbrev:
            datosEq['abrev'] = divTeamAbrev.getText().strip()
            datosMD = embeddedDataEquipos['eqData'][embeddedDataEquipos['eqAbrev2eqId'][datosEq['abrev']]]
            datosEq.update({k: datosMD[k] for k in CAMPOSDEEQUIPOAMOVER if k in datosMD})

        divTeamScore = divEq.find('p', {'class': reDatosEqPScore})
        if divTeamScore:
            puntosSTR = divTeamScore.getText()
            if puntosSTR.strip() != "":
                try:
                    datosEq['puntos'] = int(puntosSTR)
                except ValueError as exc:
                    logging.error("DivTeam no tiene puntos %s", divEq.prettify())
                    logging.error("Partido %s", divData.prettify())
                    raise exc
    return datosEq


rondaId2fasePlayOff: dict = {291: 'final', 293: 'cuartos de final', 292: 'semifinal'}


def MDround2roundData(jornada: dict) -> dict:
    result = {'jorId': jornada['id'], 'jornada': jornada['roundNumber'], 'jornadaMD': jornada['roundNumber'],
              'esPlayOff': (jornada['subphase'] is not None), 'fasePlayOff': None, 'partRonda': None}

    if result['esPlayOff']:
        result['fasePlayOff'] = rondaId2fasePlayOff[jornada['subphase']['id']]
        result['partRonda'] = jornada['subphase']['subphaseNumber']
        result['jornada'] = numPartidoPO2jornada(result['fasePlayOff'], result['partRonda'])

    result['infoJornada'] = infoJornada(jornada=result['jornada'], esPlayOff=result['esPlayOff'],
                                        fasePlayOff=result['fasePlayOff'],
                                        partRonda=result['partRonda'])

    return result

import logging
import re
from collections import defaultdict
from copy import copy, deepcopy
from time import gmtime

import pandas as pd
from CAPcore.Misc import FORMATOtimestamp, listize, onlySetElement
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage

from Utils.FechaHora import NEVER, PATRONFECHA, PATRONFECHAHORA, fecha2fechaCalDif
from Utils.Web import getObjID, prepareDownloading
from .Constants import URL_BASE, PLAYOFFFASE

logger = logging.getLogger()

calendario_URLBASE = "http://www.acb.com/calendario"

# http://www.acb.com/calendario/index/temporada_id/2018
# http://www.acb.com/calendario/index/temporada_id/2019/edicion_id/952
template_CALENDARIOYEAR = "http://www.acb.com/calendario/index/temporada_id/{year}"
template_CALENDARIOFULL = "http://www.acb.com/calendario/index/temporada_id/{year}/edicion_id/{compoID}"
template_PARTIDOSEQUIPO = "http://www.acb.com/club/partidos/id/{idequipo}"

ETIQubiq = ['local', 'visitante']

UMBRALbusquedaDistancia = 1  # La comparación debe ser >

CALENDARIOEQUIPOS = dict()


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
        calendarioData = content.data

        for divJ in calendarioData.find_all("div", {"class": "cabecera_jornada"}):
            datosCab = procesaCab(divJ)

            currJornada: int = int(datosCab['jornada'])

            divPartidos = divJ.find_next_sibling("div", {"class": "listado_partidos"})

            self.Jornadas[currJornada] = self.procesaBloqueJornada(divPartidos, datosCab, **kwargs)

        self.actualizaDatosPlayoffJornada()

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

        for jNum, jData in self.Jornadas.items():
            if not jData['esPlayoff']:
                continue

            idsCur: set = jData['idEmparej']
            curBlockStarts = jNum
            for jAux in range(jNum - 1, 0, -1):
                if not self.Jornadas[jAux]['esPlayoff']:
                    break
                id2compare: set = self.Jornadas[jAux]['idEmparej']
                if not idsCur.intersection(id2compare):
                    break
                curBlockStarts = jAux
            primJBloque = self.Jornadas[curBlockStarts]
            numGBloque = primJBloque['numPartidos']
            jData['fasePlayoff'] = PLAYOFFFASE[numGBloque]
            jData['partFasePlayoff'] = jNum - curBlockStarts + 1

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
        logger.info("descargaCalendario")
        browser, config = prepareDownloading(browser, config)

        if self.url is None:
            pagCalendario = downloadPage(self.urlbase, home=home, browser=browser, config=config)
            pagCalendarioData = pagCalendario.data
            divTemporadas = pagCalendarioData.find("div", {"class": "desplegable_temporada"})

            currYear = divTemporadas.find('div', {"class": "elemento"})['data-t2v-id']

            urlYear = template_CALENDARIOYEAR.format(year=self.edicion)
            if self.edicion is None:
                self.edicion = currYear
                pagYear = pagCalendario
            else:
                listaTemporadas = {x['data-t2v-id']: x.get_text() for x in
                                   divTemporadas.find_all('div', {"class": "elemento"})}
                if self.edicion not in listaTemporadas:
                    raise KeyError(f"Temporada solicitada {self.edicion} no está entre las "
                                   f"disponibles ({', '.join(listaTemporadas.keys())})")

                pagYear = downloadPage(urlYear, home=None, browser=browser, config=config)

            pagYearData = pagYear.data

            divCompos = pagYearData.find("div", {"class": "desplegable_competicion"})
            listaCompos = {x['data-t2v-id']: x.get_text() for x in divCompos.find_all('div', {"class": "elemento"})}
            compoClaves = compo2clave(listaCompos)

            priCompoID = divCompos.find('div', {"class": "elemento_seleccionado"}).find('input')['value']

            if self.competicion not in compoClaves:
                listaComposTxt = [f"{k} = '{listaCompos[v]}'" for k, v in compoClaves.items()]
                compo = self.competicion
                listaCompos = ", ".join(listaComposTxt)
                raise KeyError(f"Compo solicitada {compo} no disponible. Disponibles: {listaCompos}")

            self.url = template_CALENDARIOFULL.format(year=self.edicion, compoID=compoClaves[self.competicion])

            if compoClaves[self.competicion] == priCompoID:
                result = pagYear
            else:
                result = downloadPage(self.url, browser=browser, home=None, config=config)
        else:
            result = downloadPage(self.url, browser=browser, home=None, config=config)

        return result

    def procesaBloqueJornada(self, divDatos, dictCab, **kwargs):
        # TODO: incluir datos de competicion
        result = dict()
        result['nombre'] = dictCab['comp']
        result['jornada'] = int(dictCab['jornada'])
        result['partidos'] = []
        result['pendientes'] = []
        result['equipos'] = set()
        result['idEmparej'] = set()

        # print(divPartidos)
        for artP in divDatos.find_all("article", {"class": "partido"}):
            datosPart = self.procesaBloquePartido(dictCab, artP)

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
        result['esPlayoff'] = None
        result['numPartidos'] = len(result['partidos']) + len(result['pendientes'])
        return result

    def procesaBloquePartido(self, datosJornada, divPartido):
        # TODO: incluir datos de competicion
        resultado = dict()
        resultado['pendiente'] = True
        resultado['fechaPartido'] = NEVER
        resultado['jornada'] = datosJornada['jornada']

        resultado['cod_competicion'] = self.competicion
        resultado['cod_edicion'] = self.edicion

        datosPartEqs = dict()

        for eqUbic, div in zip(ETIQubiq, divPartido.find_all("div", {"class": "logo_equipo"})):
            auxDatos = datosPartEqs.get(eqUbic.capitalize(), {})
            image = div.find("img")
            imageURL = mergeURL(self.urlbase, image['src'])
            imageALT = image['alt']
            auxDatos.update({'icono': imageURL, 'imageTit': imageALT})
            datosPartEqs[eqUbic.capitalize()] = auxDatos

        for eqUbic in ETIQubiq:
            auxDatos = datosPartEqs.get(eqUbic.capitalize(), {})
            divsEq = divPartido.find_all("div", {"class": eqUbic})
            infoEq = procesaDivsEquipo(divsEq)
            auxDatos.update(infoEq)
            self.nuevaTraduccionEquipo2Codigo(nombres=[infoEq['nomblargo'], infoEq['nombcorto']], abrev=infoEq['abrev'],
                                              idEq=None)
            datosPartEqs[eqUbic.capitalize()] = auxDatos

        resultado['equipos'] = datosPartEqs
        resultado['loc2abrev'] = {k: v['abrev'] for k, v in datosPartEqs.items()}
        resultado['abrev2loc'] = {v['abrev']: k for k, v in datosPartEqs.items()}
        resultado['participantes'] = {v['abrev'] for v in datosPartEqs.values()}
        resultado['claveEmparejamiento'] = self.idGrupoEquiposNorm(resultado['participantes'])

        if 'enlace' in datosPartEqs['Local']:
            resultado['pendiente'] = False
            linkGame = datosPartEqs['Local']['enlace']
            resultado['url'] = mergeURL(self.url, linkGame)
            resultado['resultado'] = {k: v['puntos'] for k, v in datosPartEqs.items()}
            resultado['partido'] = getObjID(linkGame)

        else:
            divTiempo = divPartido.find('div', {"class": "info"})

            if divTiempo:
                auxFecha = divTiempo.find('span', {"class": "fecha"}).next
                auxHora = divTiempo.find('span', {"class": "hora"}).get_text()
                if isinstance(auxFecha, str) and auxFecha != '':
                    cadFecha = auxFecha.lower()
                    cadHora = auxHora.strip() if auxHora else None
                    try:
                        resultado['fechaPartido'] = procesaFechaHoraPartido(cadFecha.strip(), cadHora, datosJornada)
                    except ValueError as err:
                        print(err)
                        resultado['fechaPartido'] = NEVER

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
        result = ",".join(map(str, sorted([onlySetElement(self.tradEquipos['c2i'][e]) for e in conjAbrevs])))
        return result

    def jornadasCompletas(self):
        """
        Devuelve las IDs de jornadas para las que se han jugado todos los partidos
        :return: set con las jornadas para las que no quedan partidos (el id, entero)
        """
        result = {j for j, data in self.Jornadas.items() if len(data['pendientes']) == 0}
        return result

    def cal2dict(self):

        result = {'pendientes': {}, 'jugados': {}}
        for data in self.Jornadas.values():
            for pend in data['pendientes']:
                result['pendientes'][p2DictK(self, pend)] = fecha2fechaCalDif(pend['fechaPartido'])
            for jug in data['partidos']:
                result['jugados'][p2DictK(self, jug)] = jug['url']

        return result


def BuscaCalendario(url=URL_BASE, home=None, browser=None, config=None):
    if config is None:
        config = dict()
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
    result = dict()

    for idComp, label in listaCompos.items():
        if 'liga' in label.lower():
            result['LACB'] = idComp
        elif 'supercopa' in label.lower():
            result['SCOPA'] = idComp
        elif 'copa' in label.lower():
            result['COPA'] = idComp

    return result


def procesaCab(cab):
    """
    Extrae datos relevantes de la cabecera de cada jornada en el calendario
    :param cab: div que contiene la cabecera COMPLETA
    :return:  {'comp': 'Liga Endesa', 'yini': '2018', 'yfin': '2019', 'jor': '46'}
    """
    resultado = dict()
    cadL = cab.find('div', {"class": "float-left"}).text
    cadR = cab.find('div', {"class": "fechas"}).text
    resultado['nombreJornada'] = cadL
    resultado['fechasJornada'] = cadR

    patronL = r'(?P<comp>.*) (?P<yini>\d{4})-(?P<yfin>\d{4})\s+(:?-\s+(?P<extraComp>.*)\s+)?- JORNADA (?P<jornada>\d+)'

    patL = re.match(patronL, cadL)
    if patL:
        dictFound = patL.groupdict()
        resultado.update(dictFound)
        if cadR != '':
            try:
                resultado['auxFechas'] = procesaFechasJornada(cadR)
            except ValueError as exc:
                raise ValueError(f"procesaCab: {cab} RE: problemas procesando fechas de '{cadR}': '{exc}'") from exc
    else:
        raise ValueError(f"procesaCab: valor '{cadL}' no casa RE '{patronL}'")

    return resultado


def procesaFechasJornada(cadFechas):
    resultado = dict()

    mes2n = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10,
             'nov': 11, 'dic': 12}

    patronBloqueFechas = r'^(?P<dias>\d{1,2}(-\d{1,2})*)\s+(?P<mes>\w+)\s+(?P<year>\d{4})$'

    bloques = list()
    cadWrk = cadFechas.lower().strip()

    for bY in cadWrk.split(' y '):
        for b in bY.strip().split(','):
            bloques.append(b.strip())

    for b in bloques:
        reFecha = re.match(patronBloqueFechas, b.strip())
        if reFecha:
            yearN = int(reFecha['year'].strip())
            for d in reFecha['dias'].split("-"):
                diaN = int(d.strip())
                cadResult = f"{yearN:04d}-{mes2n[reFecha['mes']]:02d}-{diaN:02d}"
                if diaN in resultado:
                    resultado[diaN].add(cadResult)
                else:
                    resultado[diaN] = {cadResult}
        else:
            raise ValueError(f"procesaFechasJornada: {cadFechas} RE: '{b}' no casa patrón '{patronBloqueFechas}'")

    return resultado


def procesaDivsEquipo(divList):
    resultado = dict()
    resultado['haGanado'] = None

    for d in divList:
        if 'equipo' in d.attrs['class']:
            resultado['abrev'] = d.find('span', {"class": "abreviatura"}).get_text().strip()
            resultado['nomblargo'] = d.find('span', {"class": "nombre_largo"}).get_text().strip()
            resultado['nombcorto'] = d.find('span', {"class": "nombre_corto"}).get_text().strip()
        elif 'resultado' in d.attrs['class']:
            resultado['puntos'] = int(d.find('a').get_text().strip())
            resultado['enlace'] = d.find('a').attrs['href']
            resultado['haGanado'] = 'ganador' in d.attrs['class']
        else:
            raise ValueError(f"procesaDivsEquipo: CASO NO TRATADO: {str(d)}")

    return resultado


def procesaFechaHoraPartido(cadFecha, cadHora, datosCab):
    resultado = NEVER
    diaSem2n = {'lun': 0, 'mar': 1, 'mié': 2, 'jue': 3, 'vie': 4, 'sáb': 5, 'dom': 6}
    patronDiaPartido = r'^(?P<diasem>\w+)\s(?P<diames>\d{1,2})$'

    reFechaPart = re.match(patronDiaPartido, cadFecha.strip())

    if reFechaPart:
        if cadHora is None:
            cadHora = "00:00"
        diaSemN = diaSem2n[reFechaPart['diasem']]
        diaMesN = int(reFechaPart['diames'])

        auxFechasN = deepcopy(datosCab['auxFechas'])[diaMesN]

        if len(auxFechasN) > 1:
            pass  # Caso tratado en destino
        else:
            cadFechaFin = auxFechasN.pop()
            cadMezclada = f"{cadFechaFin.strip()} {cadHora.strip()}"
            try:
                fechaPart = pd.to_datetime(cadMezclada)
                resultado = fechaPart
            except ValueError:
                print(f"procesaFechaHoraPartido: '{cadFechaFin}' no casa RE '{FORMATOtimestamp}'")
                resultado = NEVER

    else:
        raise ValueError(f"RE: '{cadFecha}' no casa patrón '{patronDiaPartido}'")

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
    result = dict()
    result['jornadas'] = dict()

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
    jor = datosPart['jornada']
    idLoc = onlySetElement(cal.tradEquipos['c2i'][datosPart['loc2abrev']['Local']])
    idVis = onlySetElement(cal.tradEquipos['c2i'][datosPart['loc2abrev']['Visitante']])
    result = "#".join((jor, idLoc, idVis))
    return result


def dictK2partStr(cal: CalendarioACB, partK: str) -> str:
    jor, idLoc, idVis = partK.split('#')
    abrLoc = list(cal.tradEquipos['i2c'][idLoc])[-1]
    abrVis = list(cal.tradEquipos['i2c'][idVis])[-1]

    result = f"J{int(jor):02}: {abrLoc}-{abrVis}"
    return result

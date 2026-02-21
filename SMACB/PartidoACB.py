import logging
import re
from collections.abc import Iterable
from compression import zstd
from itertools import product
from pickle import dumps
from traceback import print_exc
from typing import Optional, Dict, Tuple, Union, List, Any

import numpy as np
import pandas as pd
from CAPcore.Misc import BadParameters, BadString, extractREGroups, copyDictWithTranslation, getUTC, \
    createDictFromGenerator, iterable2quotedString
from CAPcore.Web import downloadPage, extractGetParams, DownloadedPage, mergeURL
from babel.numbers import parse_number
from bs4 import Tag

import SMACB.FichaPersona as FP
from Utils.BoWtraductor import RetocaNombreJugador
from Utils.FechaHora import PATRONFECHA, PATRONFECHAHORA
from Utils.ParseoData import ProcesaTiempo
from Utils.ProcessMDparts import procesaMDresInfoPeriodos, procesaMDresEstadsCompar, procesaMDresInfoRachas, \
    procesaMDresCartaTiro, procesaMDjugadas, jugadaSort, jugada2str, jugadaKey2sort, jugadaTag2Desc, jugadaKey2str, \
    procesaMDboxscore, procesaMDavailableContent, procesaMDresDatosPartido
from Utils.Web import getObjID, prepareDownloading, extractPagDataScripts
from .Constants import (bool2esp, haGanado2esp, local2esp, LocalVisitante, OtherLoc, titular2esp, REGEX_JLR,
                        REGEX_PLAYOFF, infoJornada, numPartidoPO2jornada, POLABEL2FASE, DEFTZ)
from .PlantillaACB import PlantillaACB

templateURLficha = "https://www.acb.com/fichas/%s%i%03i.php"


class PartidoACB:

    def __init__(self, **kwargs):

        self.idPartido = kwargs.get('partido', None)
        self.competicion = kwargs['cod_competicion']
        self.edicion = kwargs['cod_edicion']

        self.jornada = None
        self.infoJornada: Optional[infoJornada] = None
        self.fechaPartido: Optional[pd.Timestamp] = None
        self.Pabellon: Optional[str] = None
        self.Asistencia: Optional[int] = None
        self.Arbitros = []
        self.ResultadosParciales = []
        self.prorrogas = 0
        self.timestamp = None
        self.esPlayoff: bool = False

        self.Equipos = createDictFromGenerator(LocalVisitante, lambda: {'Jugadores': []})

        self.Jugadores = {}
        self.Entrenadores = {}
        self.pendientes: Dict[str, List] = createDictFromGenerator(LocalVisitante, list)
        self.aprendidos: Dict[str, List] = createDictFromGenerator(LocalVisitante, list)
        self.metadataEnlaces: dict = kwargs.get('enlaces', {})
        self.availMD = {}
        self.metadataEmb = {}

        self.EquiposCalendario = kwargs['equipos']
        self.ResultadoCalendario = kwargs['resultado']
        self.CodigosCalendario = kwargs['loc2abrev']

        self.VictoriaLocal = None

        self.DatosSuministrados = kwargs

        self.url = kwargs['url']

        for loc in LocalVisitante:
            self.Equipos[loc]['haGanado'] = self.ResultadoCalendario[loc] > self.ResultadoCalendario[OtherLoc(loc)]

    def descargaPartido(self, home=None, browser=None, config=None):

        browser, config = prepareDownloading(browser, config)

        if not hasattr(self, 'url'):
            raise BadParameters("PartidoACB: DescargaPartido: imposible encontrar la URL del partido")

        urlPartido = self.url

        partidoPage = downloadPage(urlPartido, home=home, browser=browser, config=config)

        self.procesaPartido(partidoPage)

        # CAP: recuperar al final self.descargaEmbMetadata(home=home, browser=browser, config=config)

    def procesaPartido(self, content: DownloadedPage):
        raiser = False
        self.timestamp = getattr(content, 'timestamp', getUTC())

        if 'source' in content:
            self.url = content.source

        pagina = content.data
        tablasPartido = pagina.find("section", {"class": "contenedora_estadisticas"})
        if not tablasPartido:
            print(f"procesaPartido (W): {self.url} tablasPartidoNone", tablasPartido, pagina)

        # Encabezado de Tabla
        tabDatosGenerales = tablasPartido.find("header")

        divFecha = tabDatosGenerales.find("div", {"class": "datos_fecha"})
        self.procesaDivFechas(divFecha)

        # No merece la pena sacarlo a un método
        divArbitros = tabDatosGenerales.find("div", {"class": "datos_arbitros"})
        self.Arbitros = [(x.get_text(), x['href']) for x in divArbitros.find_all("a")]

        # No merece la pena sacarlo a un método
        divParciales = tabDatosGenerales.find("div", {"class": "parciales_por_cuarto"})
        aux = divParciales.get_text().split("\xa0")

        self.ResultadosParciales = [(int(x) for x in r.split("|")) for r in aux]

        divCabecera = pagina.find("div", {"class": "contenedora_info_principal"})
        self.procesaDivCabecera(divCabecera)

        for loc, tRes in zip(LocalVisitante, tablasPartido.find_all("section", {"class": "partido"})):
            colHeaders = extractPrefijosTablaEstads(tRes)
            self.extraeEstadsJugadores(tRes, loc, colHeaders)

            cachedTeam: Optional[PlantillaACB] = None
            newPendientes = []
            if self.pendientes[loc]:
                for datosJug in self.pendientes[loc]:
                    if datosJug['nombre'] == '':
                        localidad = ("Local" if datosJug['esLocal'] else "Visit")
                        equipo = datosJug['equipo']
                        dorsal = datosJug['dorsal']
                        posicion = ("Jugador" if datosJug['esJugador'] else "Entrenador")
                        datosJugTxt = f"{localidad} Eq: '{equipo}' Dorsal: {dorsal} {posicion}"
                        print(f"(W) Partido: {self} -> {datosJugTxt}: Datos insuficientes para encontrar ID.")
                        newPendientes.append(datosJug)
                        if datosJug['esJugador']:
                            # Admitimos la pifia para entrenador pero no para jugadores
                            raiser = True

                        continue

                    if cachedTeam is None:
                        cachedTeam = PlantillaACB(teamId=datosJug['IDequipo'], edicion=datosJug['edicion'])

                    nombreRetoc = RetocaNombreJugador(datosJug['nombre']) if ',' in datosJug['nombre'] else datosJug[
                        'nombre']

                    newCode = cachedTeam.getCode(nombre=nombreRetoc, dorsal=datosJug['dorsal'],
                                                 esTecnico=datosJug['entrenador'], esJugador=datosJug['esJugador'],
                                                 umbral=1)
                    if newCode is not None:
                        datosJug['codigo'] = newCode

                        if datosJug['esJugador']:
                            self.Jugadores[datosJug['codigo']] = datosJug
                            (self.Equipos[loc]['Jugadores']).append(datosJug['codigo'])
                        elif datosJug.get('entrenador', False):
                            self.Entrenadores[datosJug['codigo']] = datosJug
                            self.Equipos[loc]['Entrenador'] = datosJug['codigo']
                        self.aprendidos[loc].append(newCode)
                    else:
                        print(f"Imposible encontrar ID. Partido: {self}. {datosJug}")
                        newPendientes.append(datosJug)
                        raiser = True

                self.pendientes[loc] = newPendientes
            if raiser:
                raise ValueError(
                    f"procesaPartido: Imposible encontrar ({len(newPendientes)}) código(s) para ({loc}) en "
                    f"partido '"
                    f"{self.url}': {newPendientes}")

        return divCabecera

    def check(self):
        result = True

        for loc in LocalVisitante:
            if not self.Equipos[loc].get('estads', {}):
                logging.error("Partido: '{}' no se han encontrado estadisticas para {}.")
                result &= False

        return result

    def procesaDivFechas(self, divFecha):
        espTiempo = list(map(lambda x: x.strip(), divFecha.next.split("|")))

        reJornada = re.match(REGEX_JLR, espTiempo[0], re.IGNORECASE)
        if reJornada:
            self.esPlayoff = False
            self.jornada = int(reJornada.group('jornada'))
            self.infoJornada = infoJornada(jornada=self.jornada, esPlayOff=False)
        else:
            rePlayOff = re.match(REGEX_PLAYOFF, espTiempo[0], re.IGNORECASE)
            if rePlayOff:
                self.esPlayoff = True
                self.jornada = numPartidoPO2jornada(rePlayOff.group('etiqFasePOff'),
                                                    (rePlayOff.group('numPartPoff') or 1))
                self.infoJornada = infoJornada(jornada=self.jornada, esPlayOff=self.esPlayoff,
                                               fasePlayOff=rePlayOff.group('etiqFasePOff'),
                                               partRonda=int(rePlayOff.group('numPartPoff') or 1))
            else:
                raise ValueError(
                    f"Problemas sacando jornada de cabecera. RE:|{REGEX_JLR}|{REGEX_PLAYOFF}| Cadena:[{espTiempo[0]}|")

        cadTiempo = f"{espTiempo[1]} {espTiempo[2]}"
        PATRONdmyhm = r'^\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})?$'
        REhora = re.match(PATRONdmyhm, cadTiempo)
        patronH = PATRONFECHAHORA if REhora.group(2) else PATRONFECHA
        self.fechaPartido = pd.to_datetime(cadTiempo, format=patronH).tz_localize(DEFTZ)

        spanPabellon = divFecha.find("span", {"class": "clase_mostrar1280"})
        self.Pabellon = spanPabellon.get_text().strip()

        textAsistencia = spanPabellon.next_sibling.strip()

        rePublico = r".*ico:\s*(\d+\.(\d{3})*)"
        grpsAsist = extractREGroups(cadena=textAsistencia, regex=rePublico)
        self.Asistencia = parse_number(grpsAsist[0], locale='de_DE') if grpsAsist else None

    def procesaDivCabecera(self, divATratar):
        equipos = [(x.find("a")['href'], x.find("img")['title'].strip()) for x in
                   divATratar.find_all("div", {"class": "logo_equipo"})]
        puntos = [int(x.get_text()) for x in divATratar.find_all("div", {"class": "resultado"})]

        divParciales = divATratar.find("tbody")
        auxParciales = [[int(p.get_text()) for p in r.find_all("td", {"class": "parcial"})] for r in
                        divParciales.find_all("tr")]
        parciales = list(zip(*auxParciales))
        abrevs = [p.get_text() for p in divParciales.find_all("td", {"class": "equipo"})]

        for loc, pts in zip(LocalVisitante, puntos):
            self.Equipos[loc]['Puntos'] = pts
        self.ResultadosParciales = parciales
        self.VictoriaLocal = self.Equipos['Local']['Puntos'] > self.Equipos['Visitante']['Puntos']

        for loc, eq in zip(LocalVisitante, equipos):
            self.Equipos[loc]['id'] = getObjID(eq[0])
            self.Equipos[loc]['Nombre'] = eq[1]

        for loc, abrev in zip(LocalVisitante, abrevs):
            self.Equipos[loc]['abrev'] = abrev

    def procesaLineaTablaEstadistica(self, fila, headers, estado):
        result = {'competicion': self.competicion, 'edicion': self.edicion, 'jornada': self.jornada,
                  'equipo': self.Equipos[estado]['Nombre'], 'CODequipo': self.Equipos[estado]['abrev'],
                  'IDequipo': self.Equipos[estado]['id'], 'rival': self.Equipos[OtherLoc(estado)]['Nombre'],
                  'CODrival': self.Equipos[OtherLoc(estado)]['abrev'], 'IDrival': self.Equipos[OtherLoc(estado)]['id'],
                  'url': self.url, 'estado': estado, 'esLocal': (estado == "Local"),
                  'haGanado': (self.ResultadoCalendario[estado] > self.ResultadoCalendario[OtherLoc(estado)])}

        filaClass = fila.attrs.get('class', '')

        celdas = list(fila.find_all("td"))
        textos = [x.get_text().strip() for x in celdas]

        if len(textos) == len(headers):
            mergedTextos = dict(zip(headers[2:], textos[2:]))
            result['estads'] = self.procesaEstadisticas(mergedTextos)

            if 'equipo' in filaClass or 'totales' in filaClass:
                result['esJugador'] = False
                result['entrenador'] = False
                result['noAsignado'] = 'equipo' in filaClass
                result['totalEquipo'] = 'totales' in filaClass

                if result['totalEquipo']:
                    result['prorrogas'] = int(((result['estads']['Segs'] / (5 * 60)) - 40) // 5)

                    if result['estads']['P'] != self.Equipos[estado]['Puntos']:
                        print(result['estads'], self.Equipos[estado])
                        raise ValueError(f"ProcesaLineaTablaEstadistica: TOTAL '{estado}' "
                                         f"puntos '{result['estads']['P']}' "
                                         f"no casan con encabezado '{self.Equipos[estado]['Puntos']}'")
            else:  # Jugadores
                result['esJugador'] = True
                result['entrenador'] = False
                result['haJugado'] = mergedTextos['Min'] != ""

                mergedCells = dict(zip(headers, celdas))

                textoDorsal = mergedCells['D'].get_text()
                PATdorsal = r'(?P<titular>\*)?(?P<dorsal>\d+)'
                REdorsal = re.match(PATdorsal, textoDorsal)

                if REdorsal:
                    result['dorsal'] = REdorsal['dorsal']
                    result['esTitular'] = REdorsal['titular'] == '*'
                else:
                    raise ValueError(f"Texto dorsal '{textoDorsal}' no casa RE '{PATdorsal}'")

                celNombre = mergedCells['Nombre']
                result['nombre'] = celNombre.get_text()
                result['linkPersona'] = (celdas[1].find("a"))['href']
                result['urlPersona'] = mergeURL(self.url, result['linkPersona']).removesuffix('.html').replace(' ', '-')
                result['codigo'] = getObjID(result['linkPersona'], 'ver', None)
        else:
            textoC0 = celdas[0].get_text()
            if textoC0 == 'E':
                result['esJugador'] = False
                result['entrenador'] = True
                result['dorsal'] = textoC0

                celNombre = celdas[1]
                result['nombre'] = celNombre.get_text()
                result['linkPersona'] = (celdas[1].find("a"))['href']
                result['urlPersona'] = mergeURL(self.url, result['linkPersona']).removesuffix('.html').replace(' ', '-')
                result['codigo'] = getObjID(result['linkPersona'], 'ver', None)
            else:  # 5f lista de 5 faltas
                return None

        return result

    def procesaEstadisticas(self, contadores):

        result = {}

        reTiros = r"^\s*(\d+)/(\d+)\s*$"
        reRebotes = r"^\s*(\d+)\+(\d+)\s*$"
        rePorcentaje = r"^\s*(\d+)%\s*$"

        def ProcesaTiros(cadena):
            auxTemp = extractREGroups(cadena=cadena, regex=reTiros)
            if auxTemp:
                return int(auxTemp[0]), int(auxTemp[1])

            raise BadString(f"ProcesaEstadisticas:ProcesaTiros '{cadena}' no casa RE '{reTiros}'")

        def ProcesaRebotes(cadena):
            auxTemp = extractREGroups(cadena=cadena, regex=reRebotes)
            if auxTemp:
                return int(auxTemp[0]), int(auxTemp[1])

            raise BadString(f"ProcesaEstadisticas:ProcesaRebotes '{cadena}' no casa RE '{reRebotes}'")

        def ProcesaPorcentajes(cadena):
            auxTemp = extractREGroups(cadena=cadena, regex=rePorcentaje)
            if auxTemp:
                return int(auxTemp[0])

            raise BadString(f"ProcesaEstadisticas:ProcesaPorcentajes '{cadena}' no casa RE '{rePorcentaje}'")

        for key in contadores.keys():
            val = contadores[key]
            if val == "":
                continue

            if key in ['Min']:
                result['Segs'] = ProcesaTiempo(val)
            elif key in ['T2', 'T3', 'T1']:
                aux = ProcesaTiros(val)
                result[key + "-C"] = aux[0]
                result[key + "-I"] = aux[1]
            elif key in ['T2 %', 'T3 %', 'T1 %']:
                result[key.replace(" ", "")] = ProcesaPorcentajes(val)
            elif key == 'REB-D+O':
                aux = ProcesaRebotes(val)
                result["R-D"] = aux[0]
                result["R-O"] = aux[1]
            else:
                try:
                    result[key] = int(val)
                except ValueError:
                    result[key] = None
                    print_exc()
                    print(f"ProcesaEstadisticas: Error: '{key}'='{val}' converting to INT. "
                          f"URL Partido: {self.url} -> {contadores}")

        return result

    def jugadoresAdataframe(self) -> pd.DataFrame:
        typesDF = {'competicion': 'object', 'edicion': 'int64', 'jornada': 'int64', 'esLocal': 'bool',
                   'esTitular': 'bool', 'haJugado': 'bool', 'titular': 'category', 'haGanado': 'bool',
                   'enActa': 'bool', }

        dfJugs = [auxJugador2dataframe(typesDF, x, self.fechaPartido) for x in self.Jugadores.values()]
        dfResult = pd.concat(dfJugs, axis=0, ignore_index=True, sort=True).astype(typesDF)
        return dfResult

    def extraeEstadsJugadores(self, divTabla, estado, headers):
        filas = divTabla.find("tbody").find_all("tr")

        for f in filas:
            datos = self.procesaLineaTablaEstadistica(fila=f, headers=headers, estado=estado)
            if datos is None:
                continue

            if (datos.get('codigo', None) is None) and (datos['esJugador'] or datos['entrenador']):
                self.pendientes[estado].append(datos)

            if datos['esJugador']:
                self.Jugadores[datos['codigo']] = datos
                (self.Equipos[estado]['Jugadores']).append(datos['codigo'])
            elif datos.get('noAsignado', False):
                self.Equipos[estado]['NoAsignado'] = datos['estads']
            elif datos.get('totalEquipo', False):
                self.prorrogas = datos['prorrogas']
                if '+/-' in datos['estads'] and datos['estads']['+/-'] is None:
                    datos['estads']['+/-'] = (
                            self.ResultadoCalendario[estado] - self.ResultadoCalendario[OtherLoc(estado)])
                self.Equipos[estado]['estads'] = datos['estads']
            elif datos.get('entrenador', False):
                self.Entrenadores[datos['codigo']] = datos
                self.Equipos[estado]['Entrenador'] = datos['codigo']

    def partidoAdataframe(self) -> pd.DataFrame:
        infoCols = ['jornada', 'Pabellon', 'Asistencia', 'prorrogas', 'VictoriaLocal', 'url', 'competicion',
                    'edicion', 'idPartido']
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

    def haGanado(self, pers: FP.FichaPersona) -> bool:
        persId: str = pers.persId
        tipoPers: str = pers.tipoFicha

        tablaAmirar = self.Jugadores if tipoPers == "jugador" else self.Entrenadores

        if persId not in tablaAmirar:
            raise KeyError(f"haGanado: {tipoPers} {pers.alias or pers.nombre} no ha jugado partido {self}")

        return tablaAmirar[persId]['haGanado']

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

            auxEqPuntCanastas = estads['T2-C'] * 2 + estads['T3-C'] * 3
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
            auxAvail = procesaMDavailableContent(extractPagDataScripts(pag, 'availableContent'))
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
                auxResParciales = procesaMDresInfoPeriodos(extractPagDataScripts(pag, 'initialMatchHeader'))
                if auxResParciales is not None:
                    resultado['resultsParciales'] = auxResParciales
                    completion.append(True)
                else:
                    completion.append(False)

            if 'datosPartido' in resultado:
                completion.append(True)
            else:
                auxDatosPartido = procesaMDresDatosPartido(extractPagDataScripts(pag, 'initialMatchHeader'))
                if auxDatosPartido is not None:
                    resultado['datosPartido'] = auxDatosPartido
                    completion.append(True)
                else:
                    completion.append(False)

            if all(completion):
                break

        self.metadataEmb = zstd.compress(dumps(resultado))

    def generaPlantillaDummy(self, loc: str, plantillaActual: Optional[dict] = None) -> dict:
        result = {'timestamp': self.timestamp, 'edicion': self.edicion}

        def generaPlantillaJugadores(idJugs: Iterable[str]) -> Dict[str, Dict[str, str]]:
            funcResult = {}
            for idJug in idJugs:
                auxData: dict = persPartido2dictFicha(self.Jugadores[idJug])
                auxData.update({'activo': True})
                funcResult[idJug] = auxData

            return funcResult

        def generaPlantillaEntrenador(idEntr: str) -> Dict[str, Dict[str, str]]:
            auxData: dict = persPartido2dictFicha(self.Entrenadores[idEntr])
            auxData.update({'activo': True, 'dorsal': '1', 'nombre': self.Entrenadores[idEntr]['nombre']})
            funcResult = {idEntr: auxData}

            return funcResult

        if loc not in LocalVisitante:
            raise KeyError(f"Parametro 'loc' debe ser {iterable2quotedString(LocalVisitante)}. Actual: '{loc}'")

        auxPlantilla = plantillaActual or createDictFromGenerator(['jugadores', 'tecnicos', 'club'], dict)
        eqData = self.Equipos[loc]
        result['jugadores'] = auxPlantilla['jugadores']
        result['jugadores'].update(generaPlantillaJugadores(eqData['Jugadores']))
        result['tecnicos'] = auxPlantilla['tecnicos']
        result['tecnicos'].update(generaPlantillaEntrenador(eqData['Entrenador']))
        result['club'] = auxPlantilla['club']
        result['club'].update({'nombreActual': eqData['Nombre'], 'nombreOficial': eqData['Nombre']})

        return result


def auxJugador2dataframe(typesDF, jugador, fechaPartido):
    dictJugador = {'enActa': True, 'acta': 'S'}

    # Añade las estadísticas al resultado saltándose ciertas columnas no relevantes
    dictJugador.update(copyDictWithTranslation(jugador, excludes=['esJugador', 'entrenador', 'estads', 'estado']))

    if jugador['haJugado']:
        # Añade campos sacados de la página ACB
        dictJugador.update(jugador['estads'])
        typesDF.update(dict.fromkeys(jugador['estads'], 'float64'))

        # Añade campos derivados
        dictJugador['TC-I'] = dictJugador['T2-I'] + dictJugador['T3-I']
        dictJugador['TC-C'] = dictJugador['T2-C'] + dictJugador['T3-C']
        dictJugador['PTC'] = 2 * dictJugador['T2-C'] + 3 * dictJugador['T3-C']
        dictJugador['ppTC'] = dictJugador['PTC'] / dictJugador['TC-I'] if dictJugador['TC-I'] else np.nan
        dictJugador['A-BP'] = dictJugador['A'] / dictJugador['BP'] if dictJugador['BP'] else np.nan
        dictJugador['A-TCI'] = dictJugador['A'] / dictJugador['TC-I'] if dictJugador['TC-I'] else np.nan

        typesDF['ppTC'] = 'float64'
        typesDF['PTC'] = 'float64'
        typesDF['A-BP'] = 'float64'
        typesDF['A-TCI'] = 'float64'

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


def GeneraURLpartido(link):
    def CheckParameters(dictParams):
        requiredParamList = ('cod_competicion', 'cod_edicion', 'partido')
        errores = False
        missingParameters = set()

        for par in requiredParamList:
            if par not in dictParams:
                errores = True
                missingParameters.add(par)

        if errores:
            raise BadParameters(f"GeneraURLpartido: falta informacion en parámetro: {missingParameters}.")

    if isinstance(link, Tag):  # Enlace a sacado con BeautifulSoup
        link2process = link['href']
    elif isinstance(link, str):  # Cadena URL
        link2process = link
    elif isinstance(link, dict):  # Diccionario con los parametros necesarios s(sacados de la URL, se supone)
        CheckParameters(link)
        return templateURLficha % (link['cod_competicion'], int(link['cod_edicion']), int(link['partido']))
    else:
        raise TypeError(f"GeneraURLpartido: incapaz de procesar {link} ({type(link)})")

    liurlcomps = extractGetParams(link2process)
    CheckParameters(liurlcomps)
    return templateURLficha % (liurlcomps['cod_competicion'], int(liurlcomps['cod_edicion']),
                               int(liurlcomps['partido']))


def extractPrefijosTablaEstads(tablaEstads):
    """ Devuelve un array con las cabeceras de cada columna (con matices como los rebotes) y tiros
        Podría ser genérica pero Una de las celdas contiene información y no prefijo
    """

    cabTabla = tablaEstads.find("thead")
    filasCab = cabTabla.find_all("tr")

    colspans = [int(x.get('colspan', 1)) for x in filasCab[0].find_all("th")]
    coltexts = [x.get_text().strip() for x in filasCab[0].find_all("th")]

    coltexts[0] = ""  # La primera celda es el resultado del equipo. No un prefijo
    prefixes = []

    for i, v in enumerate(colspans):
        prefixes += ([coltexts[i]] * v)

    estheaders = [x.get_text().strip() for x in filasCab[1].find_all("th")]

    headers = [((x[0] + "-") if x[0] else "") + x[1] for x in zip(prefixes, estheaders)]
    assert (len(set(headers)) == len(headers))

    return headers


def procesaPaginaResumen(urlResumen: Union[str, DownloadedPage], home=None, browser=None,
                         config=None) -> Tuple[dict, DownloadedPage]:
    if isinstance(urlResumen, DownloadedPage):
        resumenPage = urlResumen
    else:
        browser, config = prepareDownloading(browser, config)
        resumenPage = downloadPage(urlResumen, home=home, browser=browser, config=config)

    resultado = {'comparativaEstads': procesaMDresEstadsCompar(
        extractPagDataScripts(resumenPage, 'initialMatchStatsComparative')),
        'infoRachas': procesaMDresInfoRachas(extractPagDataScripts(resumenPage, 'initialLeadTracker')),
        'cartaTiro': procesaMDresCartaTiro(extractPagDataScripts(resumenPage, 'initialShotmap')), }

    return resultado, resumenPage


def procesaPlayByPlay(urlJugadas: Union[str, DownloadedPage], home=None, browser=None,
                      config=None) -> Tuple[dict, DownloadedPage]:
    if isinstance(urlJugadas, DownloadedPage):
        jugadasPage = urlJugadas
    else:
        browser, config = prepareDownloading(browser, config)
        jugadasPage = downloadPage(urlJugadas, home=home, browser=browser, config=config)

    auxResult = procesaMDjugadas(extractPagDataScripts(jugadasPage, 'initialMatchPlayByPlay'))

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
        boxscorePage = downloadPage(urlBoxscore, home=home, browser=browser, config=config)

    resultado = {'boxscore': procesaMDboxscore(extractPagDataScripts(boxscorePage, 'initialStatistics')), }

    return resultado, boxscorePage


def persPartido2dictFicha(dataPers: Dict[str, Any]) -> Dict[str, str]:
    EXCLUDES = {'CODequipo', 'CODrival', 'IDequipo', 'IDrival', 'competicion', 'entrenador', 'equipo', 'esJugador',
                'esLocal', 'esTitular', 'estado', 'estads', 'haGanado', 'haJugado', 'jornada', 'linkPersona', 'rival',
                'edicion', 'url'}

    TRCAMPOS = {'codigo': 'id', 'urlPersona': 'URL', 'nombre': 'alias', }

    result = copyDictWithTranslation(dataPers, translation=TRCAMPOS, excludes=EXCLUDES)
    return result

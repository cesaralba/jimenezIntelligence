import re
from argparse import Namespace
from traceback import print_exc

import numpy as np
import pandas as pd
from babel.numbers import parse_number
from bs4 import Tag
from time import gmtime

from Utils.BoWtraductor import RetocaNombreJugador
from Utils.FechaHora import PATRONFECHAHORA, PATRONFECHA
from Utils.Misc import BadParameters, BadString, ExtractREGroups
from Utils.Web import DescargaPagina, ExtraeGetParams, getObjID
from .Constants import (BONUSVICTORIA, bool2esp, haGanado2esp, local2esp,
                        titular2esp, OtherLoc, LocalVisitante)
from .PlantillaACB import PlantillaACB

templateURLficha = "http://www.acb.com/fichas/%s%i%03i.php"


class PartidoACB(object):

    def __init__(self, **kwargs):
        self.jornada = None
        self.fechaPartido = None
        self.Pabellon = None
        self.Asistencia = None
        self.Arbitros = []
        self.ResultadosParciales = []
        self.prorrogas = 0

        self.Equipos = {x: {'Jugadores': []} for x in LocalVisitante}

        self.Jugadores = dict()
        self.Entrenadores = dict()
        self.pendientes = {x: list() for x in LocalVisitante}
        self.aprendidos = {x: list() for x in LocalVisitante}

        self.EquiposCalendario = kwargs['equipos']
        self.ResultadoCalendario = kwargs['resultado']
        self.CodigosCalendario = kwargs['loc2abrev']

        self.VictoriaLocal = None

        self.DatosSuministrados = kwargs

        self.url = kwargs['url']

        self.competicion = kwargs['cod_competicion']
        self.temporada = kwargs['cod_edicion']
        self.idPartido = kwargs.get('partido', None)

        for loc in LocalVisitante:
            self.Equipos[loc]['haGanado'] = self.ResultadoCalendario[loc] > self.ResultadoCalendario[OtherLoc(loc)]

    def descargaPartido(self, home=None, browser=None, config=Namespace()):

        if not hasattr(self, 'url'):
            raise BadParameters("PartidoACB: DescargaPartido: imposible encontrar la URL del partido")

        urlPartido = self.url

        partidoPage = DescargaPagina(urlPartido, home=home, browser=browser, config=config)

        self.procesaPartido(partidoPage)

    def procesaPartido(self, content: dict):
        raiser = False
        if 'timestamp' in content:
            self.timestamp = content['timestamp']
        else:
            self.timestamp = gmtime()
        if 'source' in content:
            self.url = content['source']

        pagina = content['data']
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

        self.ResultadosParciales = [(int(x[0]), int(x[1])) for x in map(lambda x: x.split("|"), aux)]

        divCabecera = pagina.find("div", {"class": "contenedora_info_principal"})
        self.procesaDivCabecera(divCabecera)

        for l, tRes in zip(LocalVisitante, tablasPartido.find_all("section", {"class": "partido"})):
            colHeaders = extractPrefijosTablaEstads(tRes)
            self.extraeEstadsJugadores(tRes, l, colHeaders)

            cachedTeam = None
            newPendientes = list()
            if self.pendientes[l]:
                for datosJug in self.pendientes[l]:
                    if datosJug['nombre'] == '':
                        datosJugTxt = "{localidad} Eq: '{equipo}' Dorsal: {dorsal} {posicion}".format(
                            localidad=("Local" if datosJug['esLocal'] else "Visit"),
                            equipo=datosJug['equipo'],
                            dorsal=datosJug['dorsal'],
                            posicion=("Jugador" if datosJug['esJugador'] else "Entrenador"))
                        print(f"(W) Partido: {self} -> {datosJugTxt}: Datos insuficientes para encontrar ID.")
                        newPendientes.append(datosJug)
                        if datosJug['esJugador']:
                            # Admitimos la pifia para entrenador pero no para jugadores
                            raiser = True

                        continue
                    else:
                        if cachedTeam is None:
                            cachedTeam = PlantillaACB(id=datosJug['IDequipo'], edicion=datosJug['temporada'])

                    nombreRetoc = RetocaNombreJugador(datosJug['nombre']) if ',' in datosJug['nombre'] else datosJug[
                        'nombre']

                    newCode = cachedTeam.getCode(nombre=nombreRetoc, dorsal=datosJug['dorsal'],
                                                 esTecnico=datosJug['entrenador'],
                                                 esJugador=datosJug['esJugador'], umbral=1)
                    if newCode is not None:
                        datosJug['codigo'] = newCode

                        if datosJug['esJugador']:
                            self.Jugadores[datosJug['codigo']] = datosJug
                            (self.Equipos[l]['Jugadores']).append(datosJug['codigo'])
                        elif datosJug.get('entrenador', False):
                            self.Entrenadores[datosJug['codigo']] = datosJug
                            self.Equipos[l]['Entrenador'] = datosJug['codigo']
                        self.aprendidos[l].append(newCode)
                    else:
                        print("Imposible encontrar ID. Partido: %s. %s" % (self, datosJug))
                        newPendientes.append(datosJug)
                        raiser = True

                self.pendientes[l] = newPendientes
            if raiser:
                raise ValueError("procesaPartido: Imposible encontrar (%i) código(s) para (%s) en partido '%s': %s" % (
                    len(newPendientes), l, self.url, newPendientes))

        return divCabecera

    def procesaDivFechas(self, divFecha):
        espTiempo = list(map(lambda x: x.strip(), divFecha.next.split("|")))

        reJornada = r"^JORNADA\s*(\d+)$"

        self.jornada = int(ExtractREGroups(cadena=espTiempo.pop(0), regex=reJornada)[0])
        cadTiempo = espTiempo[0] + " " + espTiempo[1]
        PATRONdmyhm = r'^\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})?$'
        REhora = re.match(PATRONdmyhm, cadTiempo)
        patronH = PATRONFECHAHORA if REhora.group(2) else PATRONFECHA
        self.fechaPartido = pd.to_datetime(cadTiempo, format=patronH)

        spanPabellon = divFecha.find("span", {"class": "clase_mostrar1280"})
        self.Pabellon = spanPabellon.get_text().strip()

        textAsistencia = spanPabellon.next_sibling.strip()

        rePublico = r".*ico:\s*(\d+\.(\d{3})*)"
        grpsAsist = ExtractREGroups(cadena=textAsistencia, regex=rePublico)
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

        for l, p in zip(LocalVisitante, puntos):
            self.Equipos[l]['Puntos'] = p
        self.ResultadosParciales = parciales
        self.VictoriaLocal = self.Equipos['Local']['Puntos'] > self.Equipos['Visitante']['Puntos']

        for l, e in zip(LocalVisitante, equipos):
            self.Equipos[l]['id'] = getObjID(e[0])
            self.Equipos[l]['Nombre'] = e[1]

        for l, a in zip(LocalVisitante, abrevs):
            self.Equipos[l]['abrev'] = a

    def procesaLineaTablaEstadistica(self, fila, headers, estado):
        result = dict()
        result['competicion'] = self.competicion
        result['temporada'] = self.temporada
        result['jornada'] = self.jornada
        result['equipo'] = self.Equipos[estado]['Nombre']
        result['CODequipo'] = self.Equipos[estado]['abrev']
        result['IDequipo'] = self.Equipos[estado]['id']
        result['rival'] = self.Equipos[OtherLoc(estado)]['Nombre']
        result['CODrival'] = self.Equipos[OtherLoc(estado)]['abrev']
        result['IDrival'] = self.Equipos[OtherLoc(estado)]['id']
        result['url'] = self.url
        result['estado'] = estado
        result['esLocal'] = (estado == "Local")
        result['haGanado'] = self.ResultadoCalendario[estado] > self.ResultadoCalendario[OtherLoc(estado)]

        filaClass = fila.attrs.get('class', '')

        celdas = list(fila.find_all("td"))
        textos = [x.get_text().strip() for x in celdas]

        if (len(textos) == len(headers)):
            mergedTextos = dict(zip(headers[2:], textos[2:]))
            estads = self.procesaEstadisticas(mergedTextos)
            result['estads'] = estads

            if 'equipo' in filaClass or 'totales' in filaClass:
                result['esJugador'] = False
                result['entrenador'] = False
                result['noAsignado'] = 'equipo' in filaClass
                result['totalEquipo'] = 'totales' in filaClass

                if result['totalEquipo']:
                    result['prorrogas'] = int(((estads['Segs'] / (5 * 60)) - 40) // 5)

                    if estads['P'] != self.Equipos[estado]['Puntos']:
                        print(estads, self.Equipos[estado])
                        raise BaseException("ProcesaLineaTablaEstadistica: TOTAL '%s' puntos '%i' "
                                            "no casan con encabezado '%i' " % (estado, estads['P'],
                                                                               self.Equipos[estado]['Puntos']))
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
                    raise ValueError("Texto dorsal '%s' no casa RE '%s'" % (textoDorsal, PATdorsal))

                celNombre = mergedCells['Nombre']
                result['nombre'] = celNombre.get_text()
                linkdata = (celdas[1].find("a"))['href']
                result['linkPersona'] = linkdata
                result['codigo'] = getObjID(linkdata, 'ver', None)
        else:
            textoC0 = celdas[0].get_text()
            if textoC0 == 'E':
                result['esJugador'] = False
                result['entrenador'] = True
                result['dorsal'] = textoC0

                celNombre = celdas[1]
                result['nombre'] = celNombre.get_text()
                linkdata = (celdas[1].find("a"))['href']
                result['linkPersona'] = linkdata
                result['codigo'] = getObjID(linkdata, 'ver', None)
            else:  # 5f lista de 5 faltas
                return None

        return result

    def procesaEstadisticas(self, contadores):

        result = {}

        reTiempo = r"^\s*(\d+):(\d+)\s*$"
        reTiros = r"^\s*(\d+)/(\d+)\s*$"
        reRebotes = r"^\s*(\d+)\+(\d+)\s*$"
        rePorcentaje = r"^\s*(\d+)%\s*$"

        def ProcesaTiempo(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reTiempo)
            if auxTemp:
                return (int(auxTemp[0]) * 60 + int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaTiempo '%s' no casa RE '%s' " % (cadena, reTiempo))

        def ProcesaTiros(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reTiros)
            if auxTemp:
                return (int(auxTemp[0]), int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaTiros '%s' no casa RE '%s' " % (cadena, reTiros))

        def ProcesaRebotes(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reRebotes)
            if auxTemp:
                return (int(auxTemp[0]), int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaRebotes '%s' no casa RE '%s' " % (cadena, reRebotes))

        def ProcesaPorcentajes(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=rePorcentaje)
            if auxTemp:
                return (int(auxTemp[0]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaPorcentajes '%s' no casa RE '%s' " %
                                (cadena, rePorcentaje))

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
                    print("ProcesaEstadisticas: Error: '%s'='%s' converting to INT. "
                          "URL Partido: %s -> %s" % (key, val, self.url, contadores))

        return (result)

    def resumenPartido(self):
        return " * J %i: %s (%s) %i - %i %s (%s) " % (self.jornada, self.EquiposCalendario['Local'],
                                                      self.CodigosCalendario['Local'],
                                                      self.ResultadoCalendario['Local'],
                                                      self.ResultadoCalendario['Visitante'],
                                                      self.EquiposCalendario['Visitante'],
                                                      self.CodigosCalendario['Visitante'])

    def jugadoresAdataframe(self):
        typesDF = {'competicion': 'object', 'temporada': 'int64', 'jornada': 'int64', 'esLocal': 'bool',
                   'esTitular': 'bool',
                   'haJugado': 'bool', 'titular': 'category', 'haGanado': 'bool', 'enActa': 'bool', 'Vsm': 'float64'}

        # 'equipo': 'object', 'CODequipo': 'object', 'rival': 'object', 'CODrival': 'object', 'dorsal': 'object'
        # 'nombre': 'object', 'codigo': 'object'

        def jugador2dataframe(jugador):
            dictJugador = dict()
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
                dictJugador['ppTC'] = dictJugador['P'] / dictJugador['TC-I'] if dictJugador['TC-I'] else np.nan
                typesDF['ppTC'] = 'float64'
                typesDF['PTC'] = 'float64'

                for k in '123C':
                    kI = f'T{k}-I'
                    kC = f'T{k}-C'
                    kRes = f'T{k}%'
                    dictJugador[kRes] = (dictJugador[kC] / dictJugador[kI] * 100.0) if dictJugador[kI] else np.nan
                    typesDF[kI] = 'float64'
                    typesDF[kC] = 'float64'
                    typesDF[kRes] = 'float64'

                bonus = BONUSVICTORIA if (jugador['haGanado'] and (jugador['estads']['V'] > 0)) else 1.0
                dictJugador['Vsm'] = jugador['estads']['V'] * bonus
            else:
                dictJugador['V'] = 0.0
                dictJugador['Vsm'] = 0.0
                typesDF['V'] = 'float64'

            dfresult = pd.DataFrame.from_dict(dictJugador, orient='index').transpose()
            dfresult['fechaPartido'] = self.fechaPartido
            dfresult['local'] = dfresult['esLocal'].map(local2esp)
            dfresult['titular'] = dfresult['esTitular'].map(titular2esp)

            dfresult['resultado'] = dfresult['haGanado'].map(haGanado2esp)
            dfresult['jugado'] = dfresult['haJugado'].map(bool2esp)

            return (dfresult)

        dfJugs = [jugador2dataframe(self.Jugadores[x]) for x in self.Jugadores]
        dfResult = pd.concat(dfJugs, axis=0, ignore_index=True, sort=True).astype(typesDF)

        return (dfResult)

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

    def partidoAdataframe(self):
        infoCols = ['jornada', 'fechaPartido', 'Pabellon', 'Asistencia', 'prorrogas', 'VictoriaLocal', 'url',
                    'competicion', 'temporada', 'idPartido']
        equipoCols = ['id', 'Nombre', 'abrev']

        infoDict = {k: self.__getattribute__(k) for k in infoCols}

        estadsDict = {loc: dict() for loc in self.Equipos}

        for loc in LocalVisitante:
            estadsDict[loc]['local'] = loc == 'Local'
            for col in equipoCols:
                estadsDict[loc][col] = self.Equipos[loc][col]
            estadsDict[loc]['haGanado'] = self.DatosSuministrados['equipos'][loc]['haGanado']
            estadsDict[loc]['convocados'] = len(self.Equipos[loc]['Jugadores'])
            estadsDict[loc]['utilizados'] = len(
                [j for j in self.Equipos[loc]['Jugadores'] if self.Jugadores[j]['haJugado']])

            estadsDict[loc].update(self.Equipos[loc]['estads'])

            estadsDict[loc]['TC-I'] = self.Equipos[loc]['estads']['T2-I'] + self.Equipos[loc]['estads']['T3-I']
            estadsDict[loc]['TC-C'] = self.Equipos[loc]['estads']['T2-C'] + self.Equipos[loc]['estads']['T3-C']

            for k in '123C':
                kI = f'T{k}-I'
                kC = f'T{k}-C'
                kRes = f'T{k}%'
                estadsDict[loc][kRes] = estadsDict[loc][kC] / estadsDict[loc][kI] * 100.0

            estadsDict[loc]['POS'] = self.Equipos[loc]['estads']['T2-I'] + self.Equipos[loc]['estads']['T3-I'] + (
                    self.Equipos[loc]['estads']['T1-I'] * 0.44) + self.Equipos[loc]['estads']['BP'] - \
                                     self.Equipos[loc]['estads']['R-O']
            estadsDict[loc]['OER'] = self.Equipos[loc]['estads']['P'] / estadsDict[loc]['POS']
            estadsDict[loc]['OERpot'] = self.Equipos[loc]['estads']['P'] / (
                    estadsDict[loc]['POS'] - self.Equipos[loc]['estads']['BP'])
            estadsDict[loc]['EffRebD'] = self.Equipos[loc]['estads']['R-D'] / (
                    self.Equipos[loc]['estads']['R-D'] + self.Equipos[OtherLoc(loc)]['estads']['R-O']) * 100.0
            estadsDict[loc]['EffRebO'] = self.Equipos[loc]['estads']['R-O'] / (
                    self.Equipos[loc]['estads']['R-O'] + self.Equipos[OtherLoc(loc)]['estads']['R-D']) * 100.0
            estadsDict[loc]['t2/tc-I'] = self.Equipos[loc]['estads']['T2-I'] / estadsDict[loc]['TC-I'] * 100.0
            estadsDict[loc]['t3/tc-I'] = self.Equipos[loc]['estads']['T3-I'] / estadsDict[loc]['TC-I'] * 100.0
            estadsDict[loc]['t2/tc-C'] = self.Equipos[loc]['estads']['T2-C'] / estadsDict[loc]['TC-C'] * 100.0
            estadsDict[loc]['t3/tc-C'] = self.Equipos[loc]['estads']['T3-C'] / estadsDict[loc]['TC-C'] * 100.0
            estadsDict[loc]['eff-t2'] = self.Equipos[loc]['estads']['T2-C'] * 2 / (
                    self.Equipos[loc]['estads']['T2-C'] * 2 + self.Equipos[loc]['estads']['T3-C'] * 3) * 100.0
            estadsDict[loc]['eff-t3'] = self.Equipos[loc]['estads']['T3-C'] * 3 / (
                    self.Equipos[loc]['estads']['T2-C'] * 2 + self.Equipos[loc]['estads']['T3-C'] * 3) * 100.0
            estadsDict[loc]['ppTC'] = (self.Equipos[loc]['estads']['T2-C'] * 2 + self.Equipos[loc]['estads'][
                'T3-C'] * 3) / estadsDict[loc]['TC-I']
            estadsDict[loc]['A/TC-C'] = self.Equipos[loc]['estads']['A'] / estadsDict[loc]['TC-C'] * 100.0
            estadsDict[loc]['A/BP'] = self.Equipos[loc]['estads']['A'] / self.Equipos[loc]['estads']['BP']
            estadsDict[loc]['RO/TC-F'] = self.Equipos[loc]['estads']['R-O'] / (
                    estadsDict[loc]['TC-I'] - estadsDict[loc]['TC-C'])

            estadsDict[loc]['Segs'] = self.Equipos[loc]['estads']['Segs'] / 5

        infoDict['Ptot'] = estadsDict['Local']['P'] + estadsDict[OtherLoc('Local')]['P']
        infoDict['POStot'] = estadsDict['Local']['POS'] + estadsDict[OtherLoc('Local')]['POS']

        estadsDF = pd.DataFrame.from_dict(data=estadsDict, orient='index')

        infoDF = pd.DataFrame.from_dict(data=[infoDict], orient='columns').reset_index(drop=True)
        localDF = estadsDF.loc[estadsDF['local']].reset_index(drop=True)
        visitanteDF = estadsDF.loc[~estadsDF['local']].reset_index(drop=True)

        result = pd.concat([infoDF, localDF, visitanteDF], axis=1, keys=['Info', 'Local', 'Visitante'])
        result.index = result['Info', 'url']
        result.index.name = 'url'
        return result

    def __str__(self):
        return "J %02i: [%s] %s (%s) %i - %i %s (%s)" % (
            self.jornada, self.fechaPartido,
            self.EquiposCalendario['Local']['nomblargo'], self.CodigosCalendario['Local'],
            self.ResultadoCalendario['Local'],
            self.ResultadoCalendario['Visitante'], self.EquiposCalendario['Visitante']['nomblargo'],
            self.CodigosCalendario['Visitante'])

    def __getitem__(self, item):
        return getattr(self, item)

    __repr__ = __str__


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
            raise BadParameters("GeneraURLpartido: falta informacion en parámetro: %s." % missingParameters)

    if type(link) is Tag:  # Enlace a sacado con BeautifulSoup
        link2process = link['href']
    elif type(link) is str:  # Cadena URL
        link2process = link
    elif type(link) is dict:  # Diccionario con los parametros necesarios s(sacados de la URL, se supone)
        CheckParameters(link)
        return templateURLficha % (link['cod_competicion'], int(link['cod_edicion']), int(link['partido']))
    else:
        raise TypeError("GeneraURLpartido: incapaz de procesar %s (%s)" % (link, type(link)))

    liurlcomps = ExtraeGetParams(link2process)
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

    for i in range(len(colspans)):
        prefixes += ([coltexts[i]] * colspans[i])

    estheaders = [x.get_text().strip() for x in filasCab[1].find_all("th")]

    headers = [((x[0] + "-") if x[0] else "") + x[1] for x in zip(prefixes, estheaders)]
    assert (len(set(headers)) == len(headers))

    return (headers)

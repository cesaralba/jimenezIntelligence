'''
Created on Dec 31, 2017

@author: calba
'''

import re
from argparse import Namespace
from time import gmtime, mktime, strftime, strptime
from traceback import print_exc

import pandas as pd
from babel.numbers import parse_number
from bs4 import Tag

from Utils.BoWtraductor import RetocaNombreJugador
from Utils.Misc import BadParameters, BadString, ExtractREGroups
from Utils.Web import DescargaPagina, ExtraeGetParams, getObjID

from .PlantillaACB import PlantillaACB
from .SMconstants import (BONUSVICTORIA, bool2esp, haGanado2esp, local2esp,
                          titular2esp)

templateURLficha = "http://www.acb.com/fichas/%s%i%03i.php"

LocalVisitante = ('Local', 'Visitante')


class PartidoACB(object):

    def __init__(self, **kwargs):
        self.Jornada = None
        self.FechaHora = None
        self.Pabellon = None
        self.Asistencia = None
        self.Arbitros = []
        self.ResultadosParciales = []
        self.prorrogas = 0

        self.Equipos = {x: {'Jugadores': [], 'haGanado': False} for x in LocalVisitante}

        self.Jugadores = dict()
        self.Entrenadores = dict()
        self.pendientes = {x: list() for x in LocalVisitante}
        self.aprendidos = {x: list() for x in LocalVisitante}

        self.EquiposCalendario = kwargs['equipos']
        self.ResultadoCalendario = kwargs['resultado']
        self.CodigosCalendario = kwargs['codigos']

        self.VictoriaLocal = None

        self.DatosSuministrados = kwargs

        self.url = kwargs['url']

        self.competicion = kwargs['cod_competicion']
        self.temporada = kwargs['cod_edicion']
        self.idPartido = kwargs.get('partido', None)

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
                        print("Datos insuficientes para encontrar ID. Partido: %s. %s" % (self, datosJug))
                        continue
                        # newPendientes.append(datosJug)
                        # if datosJug['esJugador']:
                        #     # Admitimos la pifia para entrenador pero no para jugadores
                        #     raiser = True
                    else:
                        if cachedTeam is None:
                            cachedTeam = PlantillaACB(id=datosJug['IDequipo'], edicion=datosJug['temporada'])

                        nombreRetoc = RetocaNombreJugador(
                            datosJug['nombre']) if ',' in datosJug['nombre'] else datosJug['nombre']

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

        self.Jornada = int(ExtractREGroups(cadena=espTiempo.pop(0), regex=reJornada)[0])
        cadTiempo = espTiempo[0] + " " + espTiempo[1]
        PATRONdmyhm = r'^\s*(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})?$'
        REhora = re.match(PATRONdmyhm, cadTiempo)
        patronH = "%d/%m/%Y %H:%M" if REhora.group(2) else "%d/%m/%Y "
        self.FechaHora = strptime(cadTiempo, patronH)

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
        result['jornada'] = self.Jornada
        result['equipo'] = self.Equipos[estado]['Nombre']
        result['CODequipo'] = self.Equipos[estado]['abrev']
        result['IDequipo'] = self.Equipos[estado]['id']
        result['rival'] = self.Equipos[OtherTeam(estado)]['Nombre']
        result['CODrival'] = self.Equipos[OtherTeam(estado)]['abrev']
        result['IDrival'] = self.Equipos[OtherTeam(estado)]['id']
        result['estado'] = estado
        result['esLocal'] = (estado == "Local")
        result['haGanado'] = self.ResultadoCalendario[estado] > self.ResultadoCalendario[OtherTeam(estado)]

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
                    result['titular'] = REdorsal['titular'] == '*'
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
        return " * J %i: %s (%s) %i - %i %s (%s) " % (self.Jornada, self.EquiposCalendario['Local'],
                                                      self.CodigosCalendario['Local'],
                                                      self.ResultadoCalendario['Local'],
                                                      self.ResultadoCalendario['Visitante'],
                                                      self.EquiposCalendario['Visitante'],
                                                      self.CodigosCalendario['Visitante'])

    def jugadoresAdataframe(self):
        typesDF = {'competicion': 'object', 'temporada': 'int64', 'jornada': 'int64', 'esLocal': 'bool',
                   'haJugado': 'bool', 'titular': 'category', 'haGanado': 'bool', 'enActa': 'bool', 'Vsm': 'float64'}

        # 'equipo': 'object', 'CODequipo': 'object', 'rival': 'object', 'CODrival': 'object', 'dorsal': 'object'
        # 'nombre': 'object', 'codigo': 'object'

        def jugador2dataframe(jugador):
            dictJugador = dict()
            dictJugador['enActa'] = True
            dictJugador['acta'] = 'S'

            for dato in jugador:
                if dato in ['esJugador', 'entrenador', 'estads', 'estado']:
                    continue
                dictJugador[dato] = jugador[dato]

            if jugador['haJugado']:
                for dato in jugador['estads']:
                    dictJugador[dato] = jugador['estads'][dato]
                    typesDF[dato] = 'float64'
                dictJugador['Vsm'] = (jugador['estads']['V'] * (BONUSVICTORIA if (
                        jugador['haGanado'] and (jugador['estads']['V'] > 0)) else 1.0)
                                      )
            else:
                dictJugador['V'] = 0.0
                dictJugador['Vsm'] = 0.0
                typesDF['V'] = 'float64'

            dfresult = pd.DataFrame.from_dict(dictJugador, orient='index').transpose()
            dfresult['Fecha'] = pd.to_datetime(mktime(self.FechaHora), unit='s')
            dfresult['local'] = dfresult['esLocal'].map(local2esp)
            dfresult['titular'] = dfresult['titular'].map(titular2esp)
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
                            self.ResultadoCalendario[estado] - self.ResultadoCalendario[OtherTeam(estado)])
                self.Equipos[estado]['estads'] = datos['estads']
            elif datos.get('entrenador', False):
                self.Entrenadores[datos['codigo']] = datos
                self.Equipos[estado]['Entrenador'] = datos['codigo']

    def __str__(self):
        return "J %02i: [%s] %s (%s) %i - %i %s (%s)" % (
            self.Jornada, strftime("%Y-%m-%d %H:%M", self.FechaHora),
            self.EquiposCalendario['Local']['nomblargo'], self.CodigosCalendario['Local'],
            self.ResultadoCalendario['Local'],
            self.ResultadoCalendario['Visitante'], self.EquiposCalendario['Visitante']['nomblargo'],
            self.CodigosCalendario['Visitante'])

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


def OtherTeam(team):
    if team == 'Local':
        return 'Visitante'
    elif team == 'Visitante':
        return 'Local'
    else:
        raise BadParameters("OtherTeam: '%s' provided. It only accept 'Visitante' or 'Local'" % team)


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

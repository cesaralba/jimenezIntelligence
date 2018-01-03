'''
Created on Dec 31, 2017

@author: calba
'''

from time import gmtime, strptime
from traceback import print_exc

from bs4 import Tag

from Utils.Misc import BadParameters, BadString, ExtractREGroups
from Utils.Web import DescargaPagina, ExtraeGetParams

templateURLficha = "http://www.acb.com/fichas/%s%i%03i.php"
reJornada = ".*J\s*(\d)\s*"
rePublico = ".*ico:(\d+)"
reArbitro = ".*rb:\s*(.*)\s*$"
reResultadoEquipo = "^\s*(.*)\s+(\d+)\s*$"

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

        self.Equipos = {}
        for x in LocalVisitante:
            self.Equipos[x] = {}
            self.Equipos[x]['Jugadores'] = []
            self.Equipos[x]['haGanado'] = False

        self.Jugadores = {}

        self.EquiposCalendario = dict(zip(LocalVisitante, kwargs['equipos']))
        self.ResultadoCalendario = dict(zip(LocalVisitante, kwargs['resultado']))
        self.CodigosCalendario = dict(zip(LocalVisitante, kwargs['codigos']))

        self.VictoriaLocal = None

        self.DatosSuministrados = kwargs

        if 'url' in kwargs:
            self.url = kwargs['url']
        else:
            if 'URLparams' in kwargs:
                self.url = GeneraURLpartido(kwargs['URLparams'])

        if 'URLparams' in kwargs:
            self.competicion = kwargs['URLparams']['cod_competicion']
            self.temporada = kwargs['URLparams']['cod_edicion']
            self.idPartido = kwargs['URLparams']['partido']

    def DescargaPartido(self, home=None, browser=None, config={}):

        if not hasattr(self, 'url'):
            raise BadParameters("PartidoACB: DescargaPartido: imposible encontrar la URL del partido")

        urlPartido = self.url

        partidoPage = DescargaPagina(urlPartido, home=home, browser=browser, config=config)

        self.ProcesaPartido(partidoPage)

    def ProcesaPartido(self, content):
        if 'timestamp' in content:
            self.timestamp = content['timestamp']
        else:
            self.timestamp = gmtime()
        if 'source' in content:
            self.url = content['source']

        tablasPartido = content['data'].find_all("table", {"class": "estadisticasnew"})

        # Encabezado de Tabla
        tabDatosGenerales = tablasPartido.pop(0)
        filas = tabDatosGenerales.find_all("tr")

        # Primera fila
        celdas = filas.pop(0).find_all("td")
        espTiempo = celdas.pop(0).get_text().split("|")
        # Jaux = ExtractREGroups(cadena=espTiempo.pop(0).strip(), regex=reJornada)
        self.Jornada = int(ExtractREGroups(cadena=espTiempo.pop(0).strip(), regex=reJornada)[0])
        self.FechaHora = strptime(espTiempo[0] + espTiempo[1], " %d/%m/%Y  %H:%M ")
        self.Pabellon = espTiempo[2].strip()
        # Paux = rePublico.match(espTiempo[3])
        # self.Asistencia = int(Paux.group(1))
        self.Asistencia = int(ExtractREGroups(cadena=espTiempo[3], regex=rePublico)[0])
        celdas.pop(0)  # Spacer
        self.prorrogas = len(celdas) - 4

        # Segunda fila
        celdas = [x.get_text().strip() for x in filas.pop(0).find_all("td")]

        # reArbitro.match(celdas.pop(0))
        self.Arbitros = [x.strip() for x in ExtractREGroups(cadena=celdas.pop(0).strip(),
                                                            regex=reArbitro)[0].split(",")]
        celdas.pop(0)  # Spacer
        aux = map(lambda x: x.split("|"), celdas)
        self.ResultadosParciales = [(int(x[0]), int(x[1])) for x in aux]

        # Datos Partido
        tabDatosGenerales = tablasPartido.pop(0)
        filas = tabDatosGenerales.find_all("tr")
        fila0 = filas.pop(0)
        fila1 = filas.pop(0)

        colHeaders = self.ExtractPrefijosTabla(fila0, fila1)

        estado = "Local"

        self.GetResultEquipo(fila0.find("td").get_text(), estado)

        while filas:
            fila = filas.pop(0)

            if "estverde" in fila.get('class', ""):
                estado = "Visitante"
                self.GetResultEquipo(fila.find("td").get_text(), estado)
                self.VictoriaLocal = self.Equipos['Local']['Puntos'] > self.Equipos['Visitante']['Puntos']
                filas.pop(0)
                continue
            datos = self.ProcesaLineaTablaEstadistica(fila=fila, headers=colHeaders, estado=estado)
            if not datos:
                continue

            if datos['esJugador']:
                (self.Equipos[estado]['Jugadores']).append(datos['codigo'])
                self.Jugadores[datos['codigo']] = datos

            elif datos.get('noAsignado', False):
                self.Equipos[estado]['NoAsignado'] = datos['estads']

            elif datos.get('totalEquipo', False):
                self.prorrogas = datos['prorrogas']
                if '+/-' in datos['estads'] and datos['estads']['+/-'] is None:
                    datos['estads']['+/-'] = (self.ResultadoCalendario[estado] -
                                              self.ResultadoCalendario[OtherTeam(estado)])
                self.Equipos[estado]['estads'] = datos['estads']

            elif datos.get('entrenador', False):
                self.Equipos[estado]['Entrenador'] = datos

            else:
                BaseException("I am missing something: {}" % datos)

        # Asigna la victoria
        if self.VictoriaLocal:
            estadoGanador = 'Local'
        else:
            estadoGanador = 'Visitante'
        self.Equipos[estadoGanador]['haGanado'] = True
        self.Equipos[estadoGanador]['Entrenador']['haGanado'] = True
        for jug in self.Equipos[estadoGanador]['Jugadores']:
            self.Jugadores[jug]['haGanado'] = True

    def ExtractPrefijosTabla(self, filacolspans, filaheaders):
        """ Devuelve un array con las cabeceras de cada columna (con matices como los rebotes) y tiros
            Podría ser genérica pero Una de las celdas contiene información y no prefijo
        """

        colspans = [int(x.get('colspan', 1)) for x in filacolspans.find_all("td")]
        coltexts = [x.get_text().strip() for x in filacolspans.find_all("td")]
        coltexts[0] = ""  # La primera celda es el resultado del equipo. No pun prefijo
        prefixes = []

        for i in range(len(colspans)):
            prefixes += ([coltexts[i]] * colspans[i])

        estheaders = [x.get_text().strip() for x in filaheaders.find_all("td")]

        headers = [((x[0] + "-") if x[0] else "") + x[1] for x in zip(prefixes, estheaders)]
        assert(len(set(headers)) == len(headers))

        return (headers)

    def ProcesaLineaTablaEstadistica(self, fila, headers, estado):
        result = dict()
        result['esJugador'] = True
        result['entrenador'] = False
        result['haJugado'] = True
        result['esLocal'] = (estado == "Local")
        textos = [x.get_text().strip() for x in fila.find_all("td")]
        celdas = fila.find_all("td")
        if (len(textos) == len(headers) - 1):  # El equipo no tiene dorsal
            result['isPlayer'] = False
            textos = [''] + textos
            celdas = [''] + celdas
        if (len(textos) == len(headers)):
            mergedTextos = dict(zip(headers[2:], textos[2:]))
            estads = self.ProcesaEstadisticas(mergedTextos)
            if None in estads.values():
                pass

            # mergedCeldas=dict(zip(headers[:2],celdas[:2])) ,mergedCeldas
            if textos[0]:
                result['titular'] = ("gristit" in celdas[0].get('class', ""))
                result['dorsal'] = textos[0]
                result['nombre'] = textos[1]
                result['haGanado'] = False
                linkdata = (celdas[1].find("a"))['href']
                linkdatapars = ExtraeGetParams(linkdata)
                result['codigo'] = linkdatapars['id']
                # (self.Equipos[estado]['Jugadores']).append(result['codigo'])
                if not estads:
                    result['haJugado'] = False

                result['estads'] = estads
                # self.Jugadores[result['codigo']]=result

            else:
                result['esJugador'] = False
                if textos[1].lower() == "equipo":
                    result['estads'] = estads
                    result['noAsignado'] = True
                    # self.Equipos[estado]['NoAsignado']=estads
                elif textos[1].lower() == "total":
                    result['totalEquipo'] = True
                    result['estads'] = estads
                    result['prorrogas'] = int(((estads['Segs'] / (5 * 60)) - 40) // 5)
                    # self.prorrogas = result['prorrogas']
                    # self.Equipos[estado]['estads']=estads
                    if estads['P'] != self.Equipos[estado]['Puntos']:
                        print(estads, self.Equipos[estado])
                        raise BaseException("ProcesaLineaTablaEstadistica: TOTAL '%s' puntos '%i' "
                                            "no casan con encabezado '%i' " % (estado, estads['P'],
                                                                               self.Equipos[estado]['Puntos']))
                else:
                    raise BaseException("ProcesaLineaTablaEstadistica: noplayer "
                                        "string '%s' unknown" % (textos[1].lower()))
        elif (len(textos) == 2):
            # Entrenador o faltas
            result['esJugador'] = False
            if textos[0].lower() == "e":
                result['entrenador'] = True
                result['nombre'] = textos[1]
                linkdata = (celdas[1].find("a"))['href']
                linkdatapars = ExtraeGetParams(linkdata)
                result['codigo'] = linkdatapars['id']
                result['haGanado'] = False
                # self.Equipos[estado]['Entrenador']=result
            elif textos[0].lower() == "5f":
                return dict()
                pass
            else:
                raise BaseException("ProcesaLineaTablaEstadistica: info string '%s' unknown" % (textos[0].lower()))

        # print(result)
        return(result)

        # print(len(textos),textos)

    def ProcesaEstadisticas(self, contadores):

        result = {}

        reTiempo = "^\s*(\d+):(\d+)\s*$"
        reTiros = "^\s*(\d+)/(\d+)\s*$"
        reRebotes = "^\s*(\d+)\+(\d+)\s*$"
        rePorcentaje = "^\s*(\d+)%\s*$"

        def ProcesaTiempo(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reTiempo)
            if auxTemp:
                return(int(auxTemp[0]) * 60 + int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaTiempo '%s' no casa RE '%s' " % (cadena, reTiempo))

        def ProcesaTiros(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reTiros)
            if auxTemp:
                return(int(auxTemp[0]), int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaTiros '%s' no casa RE '%s' " % (cadena, reTiros))

        def ProcesaRebotes(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=reRebotes)
            if auxTemp:
                return(int(auxTemp[0]), int(auxTemp[1]))
            else:
                raise BadString("ProcesaEstadisticas:ProcesaRebotes '%s' no casa RE '%s' " % (cadena, reRebotes))

        def ProcesaPorcentajes(cadena):
            auxTemp = ExtractREGroups(cadena=cadena, regex=rePorcentaje)
            if auxTemp:
                return(int(auxTemp[0]))
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

        return(result)

    def GetResultEquipo(self, cadena, estado):
        aux = ExtractREGroups(regex=reResultadoEquipo, cadena=cadena)

        if aux:
            self.Equipos[estado]['Nombre'] = aux[0]
            self.Equipos[estado]['Puntos'] = int(aux[1])
        else:
            raise BadString("GetResult: '%s' no casa RE '%s' " % (cadena, reResultadoEquipo))


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

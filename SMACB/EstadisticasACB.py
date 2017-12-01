
from mechanicalsoup import StatefulBrowser
from bs4 import Tag
from time import gmtime,strptime

from collections import defaultdict
import re
from Utils.Web import ExtraeGetParams
from Utils.Misc import ExtractREGroups,BadStringException

URL_BASE =  "http://www.acb.com"

reJornada=".*J\s*(\d)\s*"
rePublico=".*ico:(\d+)"
reArbitro=".*rb:\s*(.*)\s*$"
reResultadoEquipo="^\s*(.*)\s+(\d+)\s*$"

class CalendarioACB(object):

    def __init__(self,config={},url=URL_BASE):
        self.timestamp = gmtime
        self.URLsDownloaded= {}
        self.Partidos = {}
        self.Jornadas = {}

        self.changed = False
        self.url = url
        self.config = config
        self.browser = StatefulBrowser(soup_config={ 'features' : "html.parser"},
                           raise_on_404=True,
                           user_agent="SMparser",
                           )
        if 'verbose' in config:
            self.browser.set_verbose(self.config.verbose)

        if 'debug' in config:
            self.browser.set_debug(self.config.debug)


    def BajaCalendario(self,competicion="LACB",edicion=None):
        self.browser.open(self.url)
        callinks = self.browser.links(link_text="Calendario")
        if len(callinks)==1:
            link=callinks[0]
        else:
            raise SystemError("Too many links to Calendario. {}".format(callinks))

        if not competicion in link['href']:
            raise SystemError("Enlace '{}' no corresponde a competición {}.".format(link['href'],
                                                                                    competicion))
        self.browser.follow_link(link)
        curURL=self.browser.get_url()

        #print(self.browser.get_current_page())
        urlsToDownload = {}
        for li in self.browser.links(url_regex="stspartido.php"):
            liurl = li['href']
            if not liurl in self.URLsDownloaded:
                if not liurl in urlsToDownload:
                    urlsToDownload[liurl] = li
                    self.BajaPartido(dest=li,home=curURL)
                    break


    def BajaPartido(self,dest=None,home=None):
        partido = Partido(home=home,dest=dest,browser=self.browser )


class Partido(object):

    def __init__(self,dest,home=None,browser=None):

        datosURL=ExtraeGetParams(dest['href'])
        self.comp = datosURL['cod_competicion']
        self.temp = datosURL['cod_edicion']
        self.game = datosURL['partido']
        self.Jornada = None
        self.FechaHora = None
        self.Pabellon = None
        self.Asistencia = None
        self.Arbitros = []
        self.ResultadosParciales = []

        self.Equipos = {}
        for x in ('Local','Visitante'):
            self.Equipos[x]={}

        self.Jugadores = {}
        self.VictoriaLocal = None

        self.Prorrogas = 0

        if browser is None:
            browser=StatefulBrowser(soup_config={ 'features' : "html.parser"},
                           raise_on_404=True,
                           user_agent="SMparser",
                           )
        if home is None:
            browser.open(dest)
        else:
            browser.open(home)
            browser.follow_link(dest)

        self.url = browser.get_url()
        self.ParsePartido(browser.get_current_page())

        print(self.__dict__)

    def ParsePartido(self,content):

        #Datos muy sucios
        #partHeader=pagePartido.find("div",{"class":'titulopartidonew'})

        tablasPartido=content.find_all("table",{"class":"estadisticasnew"})

        #Encabezado de Tabla
        tabDatosGenerales=tablasPartido.pop(0)
        filas=tabDatosGenerales.find_all("tr")

        #Primera fila
        celdas=filas.pop(0).find_all("td")
        espTiempo = celdas.pop(0).get_text().split("|")
        #Jaux = ExtractREGroups(cadena=espTiempo.pop(0).strip(), regex=reJornada)
        self.Jornada=int(ExtractREGroups(cadena=espTiempo.pop(0).strip(), regex=reJornada)[0])
        self.FechaHora = strptime(espTiempo[0] + espTiempo[1]," %d/%m/%Y  %H:%M ")
        self.Pabellon = espTiempo[2].strip()
        #Paux = rePublico.match(espTiempo[3])
        #self.Asistencia = int(Paux.group(1))
        self.Asistencia = int(ExtractREGroups(cadena=espTiempo[3], regex=rePublico)[0])
        celdas.pop(0) # Spacer
        self.prorrogas = len(celdas)-4

        #Segunda fila
        celdas=[ x.get_text().strip() for x in filas.pop(0).find_all("td")]

        #reArbitro.match(celdas.pop(0))
        self.Arbitros = [ x.strip() for x in ExtractREGroups(cadena=celdas.pop(0).strip(), regex=reArbitro)[0].split(",")]
        celdas.pop(0) # Spacer
        aux = map(lambda x: x.split("|"),celdas)
        self.ResultadosParciales = [ (int(x[0]),int(x[1])) for x in aux ]

        #Datos Partido
        tabDatosGenerales=tablasPartido.pop(0)
        filas=tabDatosGenerales.find_all("tr")
        fila0=filas.pop(0)
        fila1=filas.pop(0)

        colHeaders=self.ExtractPrefijosTabla(fila0,fila1)

        estado="Local"

        self.GetResultEquipo(fila0.find("td").get_text(),estado)

        while filas:
            fila=filas.pop(0)

            if "estverde" in fila.get('class',"") :
                print("Cambio equipo!")
                estado="Visitante"
                self.GetResultEquipo(fila.find("td").get_text(),estado)
                self.VictoriaLocal = self.Equipos['Local']['Puntos'] > self.Equipos['Visitante']['Puntos']
                filas.pop(0)
                continue
            self.ProcesaLineaTablaEstadistica(fila=fila, headers=colHeaders,estado=estado)
            #print("--",fila)
            #

#         print("\n")

    def ExtractPrefijosTabla(self,filacolspans,filaheaders):
        """ Devuelve un array con las cabeceras de cada columna (con matices como los rebotes) y tiros
            Podría ser genérica pero Una de las celdas contiene información y no prefijo
        """

        colspans = [ int(x.get('colspan',1)) for x in filacolspans.find_all("td") ]
        coltexts = [ x.get_text().strip() for x in filacolspans.find_all("td")]
        coltexts[0]="" #La primera celda es el resultado del equipo. No pun prefijo
        prefixes = []

        for i in range(len(colspans)):
            prefixes += ([ coltexts[i]] * colspans[i])

        estheaders = [ x.get_text().strip() for x in filaheaders.find_all("td") ]

        headers=[ ((x[0]+"-") if x[0] else "")+x[1] for x in zip(prefixes,estheaders)]
        assert(len(set(headers)) == len(headers))

        return (headers)

    def ProcesaLineaTablaEstadistica(self,fila,headers,estado):
        textos=[x.get_text().strip() for x in fila.find_all("td")]
        celdas=fila.find_all("td")
        if (len(textos) == len(headers)-1): #El equipo no tiene dorsal
            textos = [''] + textos
            celdas = [''] + celdas
        if (len(textos) == len(headers)):
            mergedTextos=dict(zip(headers[2:],textos[2:]))
            estads = self.ProcesaEstadisticas(mergedTextos)
            print(mergedTextos)
            print(estads)

            #mergedCeldas=dict(zip(headers[:2],celdas[:2])) ,mergedCeldas



            #Estadisticas normales
            pass
        elif (len(textos) == 2):
            #Entrenador o faltas
            pass

        #print(len(textos),textos)

    def ProcesaEstadisticas(self,contadores):

        result = {}

        reTiempo = "^\s*(\d+):(\d+)\s*$"
        reTiros = "^\s*(\d+)/(\d+)\s*$"
        reRebotes = "^\s*(\d+)\+(\d+)\s*$"
        rePorcentaje = "^\s*(\d+)%\s*$"

        def ProcesaTiempo(cadena):
            auxTemp=ExtractREGroups(cadena=cadena, regex=reTiempo)
            if auxTemp:
                return(int(auxTemp[0])*60+int(auxTemp[1]))
            else:
                raise BadStringException("ProcesaEstadisticas:ProcesaTiempo '%s' no casa RE '%s' " % (cadena,reTiempo))

        def ProcesaTiros(cadena):
            auxTemp=ExtractREGroups(cadena=cadena, regex=reTiros)
            if auxTemp:
                return(int(auxTemp[0]),int(auxTemp[1]))
            else:
                raise BadStringException("ProcesaEstadisticas:ProcesaTiros '%s' no casa RE '%s' " % (cadena,reTiros))

        def ProcesaRebotes(cadena):
            auxTemp=ExtractREGroups(cadena=cadena, regex=reRebotes)
            if auxTemp:
                return(int(auxTemp[0]),int(auxTemp[1]))
            else:
                raise BadStringException("ProcesaEstadisticas:ProcesaRebotes '%s' no casa RE '%s' " % (cadena,reRebotes))

        def ProcesaPorcentajes(cadena):
            auxTemp=ExtractREGroups(cadena=cadena, regex=rePorcentaje)
            if auxTemp:
                return(int(auxTemp[0]))
            else:
                raise BadStringException("ProcesaEstadisticas:ProcesaPorcentajes '%s' no casa RE '%s' " % (cadena,rePorcentaje))

        for key in contadores.keys():
            val=contadores[key]
            if val == "":
                continue

            if key in ['Min']:
                result['Segs'] = ProcesaTiempo(val)
            elif key in ['T2','T3','T1']:
                aux=ProcesaTiros(val)
                result[key+"-C"] = aux[0]
                result[key+"-I"] = aux[1]
            elif key in ['T2 %','T3 %','T1 %']:
                result[key.replace(" ","")] = ProcesaPorcentajes(val)
            elif key == 'REB-D+O':
                aux=ProcesaRebotes(val)
                result["R-D"] = aux[0]
                result["R-O"] = aux[1]
            else:
                result[key] = int(val)

        return(result)









    def GetResultEquipo(self,cadena,estado):
        aux=ExtractREGroups(regex=reResultadoEquipo,cadena=cadena)

        if aux:
            self.Equipos[estado]['Nombre']=aux[0]
            self.Equipos[estado]['Puntos']=aux[1]
        else:
            raise BadStringException("GetResult: '%s' no casa RE '%s' " % (cadena,reResultadoEquipo)  )


class Entrenador(object):
    pass

class Jugador(object):
    pass


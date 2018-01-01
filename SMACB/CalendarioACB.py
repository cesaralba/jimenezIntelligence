import re
from collections import defaultdict
from time import gmtime

import bs4

from SMACB.PartidoACB import GeneraURLpartido
from Utils.Web import ComposeURL, DescargaPagina, ExtraeGetParams, MergeURL

URL_BASE = "http://www.acb.com"

calendario_URLBASE = "http://acb.com/calendario.php"
template_URLFICHA = "http://www.acb.com/fichas/%s%i%03i.php"


class CalendarioACB(object):

    def __init__(self, competition="LACB", edition=None, urlbase=calendario_URLBASE):
        self.timestamp = gmtime
        self.competicion = competition
        self.nombresCompeticion = defaultdict(int)
        self.edicion = edition
        self.Partidos = {}
        self.Jornadas = defaultdict(list)
        self.Equipos = defaultdict(int)
        self.equipo2prefijo = {}
        self.prefijo2equipo = {}
        self.url = urlbase

    def ComposeGameURL(self, parts):
        compo = parts.get('cod_competicion', None)
        edition = parts.get('cod_edicion', None)
        game = parts.get('partido', None)

        result = template_URLFICHA % (compo, edition, game)

        return result

    def BajaCalendario(self, home=None, browser=None, config={}):
        urlCalendario = ComposeURL(self.url, {'cod_competicion': self.competicion,
                                              'cod_edicion': self.edicion,
                                              'vd': "1",
                                              'vh': "60"})

        calendarioPage = DescargaPagina(urlCalendario, home=home, browser=browser, config=config)

        # calendarioURL = calendarioPage['source']
        calendarioData = calendarioPage['data']

        tablaCuerpo = calendarioData.table(recursive=False)[0]

        tablaCols = tablaCuerpo.find_all("td", recursive=False)
        colFechas = tablaCols[2]
        print(colFechas.__dict__.keys())

        currJornada = None
        for item in colFechas:
            if type(item) is bs4.element.NavigableString:
                continue
            elif item.name == 'div':
                divClasses = item.attrs.get('class', [])
                if ('menuseparacion' in divClasses) or ('piemenuclubs' in divClasses) or ('cuerpobusca' in divClasses):
                    continue
                elif 'titulomenuclubs' in divClasses:
                    tituloDiv = item.string
                    tituloFields = tituloDiv.split(" - ")
                    if len(tituloFields) == 1:
                        continue
                    else:
                        self.nombresCompeticion[tituloFields[0]] += 1
                    print("DIV: {}".format(item.string))
                    jornadaMatch = re.match("JORNADA\s+(\d+)", tituloFields[1])
                    if jornadaMatch:  # Liga Endesa 2017-18 - JORNADA 34
                        currJornada = int(jornadaMatch.groups()[0])
                        continue
                    else:  # Liga Endesa 2017-18 - Calendario jornadas - Liga Regular
                        currJornada = None
                        # TODO: Sacar nombres de partidos de playoff
                else:
                    print("DIV Unprocessed: ", item.attrs)
            elif item.name == 'table':
                self.ProcesaTablaJornada(item, currJornada)
            elif item.name in ('br'):
                continue
            else:
                print("Unexpected: ", item, item.__dict__.keys())

        return

    def ProcesaTablaJornada(self, tagTabla, currJornada):
        for row in tagTabla.find_all("tr"):
            cols = row.find_all("td", recursive=False)

            equipos = [x.strip() for x in cols[1].string.split(" - ")]
            for team in equipos:
                self.Equipos[team] += 1

            # si el partido ha sucedido, hay un enlace a las estadisticas en la col 0 (tambien en la del resultado)
            linksCol0 = cols[0].find_all("a")
            if linksCol0:
                linkGame = linksCol0[0]
                linkOk = GeneraURLpartido(linkGame)
                paramsURL = ExtraeGetParams(linkGame['href'])
            else:  # No ha habido partido
                continue
            partido = cols[1].string
            resultado = cols[2].string.strip()

            self.Partidos[linkOk] = {'params': paramsURL, 'partido': partido, 'resultado': resultado,
                                     'jornada': currJornada, 'equipos': equipos, }
            self.Jornadas[currJornada].append(linkOk)

#     def BajaPartido(self, dest=None, home=None):
#         print("Calendario.BajaPartido: DEST ", dest, " HOME ", home)
#         partido = Partido()
#         gameData = DescargaPagina(dest, home, self.browser)
#         partido.SOURCE = gameData['source']
#         datosURL = ExtraeGetParams(dest['href'])
#         partido.comp = datosURL['cod_competicion']
#         partido.temp = datosURL['cod_edicion']
#         partido.game = datosURL['partido']
#
#         partido.ParsePartido(gameData['data'])
#         # print(partido.__dict__)


def BuscaCalendario(url=URL_BASE, home=None, browser=None, config={}):

    link = None
    indexPage = DescargaPagina(url, home, browser, config)

    index = indexPage['data']

    # print (type(index),index)

    callinks = index.find_all("a", text="Calendario")

    if len(callinks) == 1:
        link = callinks[0]
    else:
        for auxlink in callinks:
            if 'calendario.php' in auxlink['href']:
                link = auxlink
                break
        else:
            raise SystemError("Too many links to Calendario. {}".format(callinks))

    result = MergeURL(url, link['href'])

    return result

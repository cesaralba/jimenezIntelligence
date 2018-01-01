import re
from collections import defaultdict
from copy import copy
from time import gmtime

import bs4

from SMACB.PartidoACB import GeneraURLpartido
from Utils.Misc import CompareBagsOfWords
from Utils.Web import ComposeURL, DescargaPagina, ExtraeGetParams, MergeURL

URL_BASE = "http://www.acb.com"

calendario_URLBASE = "http://acb.com/calendario.php"
template_URLFICHA = "http://www.acb.com/fichas/%s%i%03i.php"


class CalendarioACB(object):

    def __init__(self, competition="LACB", edition=None, urlbase=calendario_URLBASE):
        self.timestamp = gmtime()
        self.competicion = competition
        self.nombresCompeticion = defaultdict(int)
        self.edicion = edition
        self.Partidos = {}
        self.Jornadas = {}
        self.equipo2codigo = {}
        self.codigo2equipo = defaultdict(set)
        self.url = urlbase

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

        # Tomamos toda la informacion posible de la pagina del calendario.
        currJornada = None
        tablaPlayoffs = False
        for item in colFechas:
            if type(item) is bs4.element.NavigableString:  # Retornos de carro y cosas así
                continue
            elif item.name == 'div':
                divClasses = item.attrs.get('class', [])
                if (('menuseparacion' in divClasses) or ('piemenuclubs' in divClasses) or
                   ('cuerpobusca' in divClasses) or ('titulomenuclubsl' in divClasses)):
                    continue  # DIV estéticos o que no aportan información interesante
                elif 'titulomenuclubs' in divClasses:
                    tituloDiv = item.string
                    tituloFields = tituloDiv.split(" - ")
                    if len(tituloFields) == 1:  # Encabezado Selector de Jornadas a mostrar
                        continue
                    else:
                        self.nombresCompeticion[tituloFields[0]] += 1

                    jornadaMatch = re.match("JORNADA\s+(\d+)", tituloFields[1])
                    if jornadaMatch:  # Liga Endesa 2017-18 - JORNADA 34
                        currJornada = int(jornadaMatch.groups()[0])
                        self.Jornadas[currJornada] = dict()
                        self.Jornadas[currJornada]['nombre'] = tituloFields[1]
                        self.Jornadas[currJornada]['partidos'] = []
                        self.Jornadas[currJornada]['equipos'] = set()
                        self.Jornadas[currJornada]['esPlayoff'] = False
                        continue
                    else:  # Liga Endesa 2017-18 - Calendario jornadas - Liga Regular
                        currJornada = None
                        if 'playoff' in tituloFields[2].lower():
                            tablaPlayoffs = True
                        else:
                            tablaPlayoffs = False

                elif ('cuerponaranja' in divClasses):  # Selector para calendario de clubes
                    self.ProcesaSelectorClubes(item)
                elif ('tablajornadas' in divClasses):  # Selector para calendario de clubes
                    if tablaPlayoffs:
                        self.ProcesaTablaCalendarioJornadas(item)
                    else:
                        continue
                else:
                    print("DIV Unprocessed: ", item.attrs)
            elif item.name == 'table':
                self.ProcesaTablaJornada(item, currJornada)
            elif item.name in ('br'):  # Otras cosas que no interesan
                continue
            else:
                print("Unexpected: ", item, item.__dict__.keys())

        for jornada in self.Jornadas:
            if not self.Jornadas[jornada]['partidos']:
                continue

            for partido in self.Jornadas[jornada]['partidos']:
                self.Partidos[partido]['esPlayoff'] = self.Jornadas[jornada]['esPlayoff']

        # Detecta los cambios de nombre de equipo
        self.GestionaNombresDeEquipo()

    def ProcesaTablaJornada(self, tagTabla, currJornada):
        for row in tagTabla.find_all("tr"):
            cols = row.find_all("td", recursive=False)

            equipos = [x.strip() for x in cols[1].string.split(" - ")]
            for equipo in equipos:
                (self.Jornadas[currJornada]['equipos']).add(equipo)

            # si el partido ha sucedido, hay un enlace a las estadisticas en la col 0 (tambien en la del resultado)
            linksCol0 = cols[0].find_all("a")

            if linksCol0:
                linkGame = linksCol0[0]
                linkOk = GeneraURLpartido(linkGame)
                partido = cols[1].string
                resultado = cols[2].string.strip()

                paramsURL = ExtraeGetParams(linkGame['href'])
                self.Partidos[linkOk] = {'params': paramsURL, 'partido': partido, 'resultado': resultado,
                                         'jornada': currJornada, 'equipos': equipos, }
                (self.Jornadas[currJornada]['partidos']).append(linkOk)
            else:  # No ha habido partido
                continue

    def ProcesaSelectorClubes(self, tagForm):
        optionList = tagForm.find_all("option")
        for optionTeam in optionList:
            equipoCodigo = optionTeam['value']
            equipoNombre = optionTeam.string
            if equipoCodigo == "0":
                continue
            self.equipo2codigo[equipoNombre] = equipoCodigo
            self.codigo2equipo[equipoCodigo].add(equipoNombre)

    def ProcesaTablaCalendarioJornadas(self, tagTabla):
        for table in tagTabla.find_all("table", attrs={'class': 'jornadas'}):
            for row in table.find_all("tr"):
                cols = row.find_all("td", recursive=False)
                if len(cols) == 2:  # Encabezamiento tabla
                    continue
                currJornada = int(cols[1].string)
                if currJornada not in self.Jornadas:
                    self.Jornadas[currJornada] = dict()
                    self.Jornadas[currJornada]['partidos'] = []
                    self.Jornadas[currJornada]['equipos'] = set()

                tituloFields = cols[2].string.split(":")
                self.Jornadas[currJornada]['nombre'] = tituloFields[0].strip()
                self.Jornadas[currJornada]['esPlayoff'] = True

    def GestionaNombresDeEquipo(self):
        """ Intenta tener en cuenta los nombres de equipos que cambian a lo largo de la temporada (patrocinios)
        """

        codigosTemporada = set(self.codigo2equipo.keys())
        combinacionesNoUsadas = dict()

        for jornada in sorted(self.Jornadas.keys(), reverse=True):
            if self.Jornadas[jornada]['esPlayoff']:
                continue

            if not self.Jornadas[jornada]['equipos']:
                continue

            codigosUsados = set()
            equiposNoAsignados = set()
            for equipo in self.Jornadas[jornada]['equipos']:
                if equipo in self.equipo2codigo:
                    codigosUsados.add(self.equipo2codigo[equipo])
                else:
                    equiposNoAsignados.add(equipo)
            codigosNoUsados = codigosTemporada - codigosUsados

            if not equiposNoAsignados:  # Se asignado todo!
                continue

            # TODO: Habra que hacer algo para cuando haya equipos impares

            # busca similitures entre el nombre que aparece en el formulario (recortado) y el de las jornadas
            auxEquiposNoAsignados = copy(equiposNoAsignados)
            for equipo in auxEquiposNoAsignados:
                auxCodigosNoUsados = copy(codigosNoUsados)
                for codigo in auxCodigosNoUsados:
                    nombresRef = list(self.codigo2equipo[codigo])
                    compCadenas = dict(zip(nombresRef, [CompareBagsOfWords(equipo, x) for x in nombresRef]))
                    if max(compCadenas.values()) > 1:
                        # sortedComps = sorted(compCadenas.items(), key=itemgetter(1),reverse=True)
                        self.codigo2equipo[codigo].add(equipo)
                        self.equipo2codigo[equipo] = codigo
                        equiposNoAsignados.remove(equipo)
                        codigosNoUsados.remove(codigo)

            # Caso trivial, sólo queda uno por asignar
            if len(codigosNoUsados) == 1 and len(equiposNoAsignados) == 1:
                codigo = codigosNoUsados.pop()
                equipo = equiposNoAsignados.pop()
                self.equipo2codigo[equipo] = codigo
                (self.codigo2equipo[codigo]).add(equipo)
                continue

            if codigosNoUsados:
                combinacionesNoUsadas["|".join(sorted(list(codigosNoUsados)))] = equiposNoAsignados
            # nombresConocidos = dict(zip(codigosNoUsados, [self.codigo2equipo[k] for k in codigosNoUsados] ))

        if not combinacionesNoUsadas:
            return
        else:
            print(combinacionesNoUsadas)

    #         return
    #
    #         cambios = True
    #
    #         while cambios:
    #             cambios = False
    #             claves2codigos = dict()
    #
    #             cambioClavesConjuntos = False
    #
    #             for k in combinacionesNoUsadas:
    #                 codigos = set(k.split("|"))
    #                 claves2codigos[k] = codigos
    #
    #             for c in combinations(combinacionesNoUsadas,2):
    #                 cx = claves2codigos[c[0]]
    #                 cy = claves2codigos[c[1]]
    #                 ex = combinacionesNoUsadas[c[0]]
    #                 ey = combinacionesNoUsadas[c[1]]
    #
    #                 print(c,cx,cy,ex,ey)
    #                 continue
    #
    #                 diffxy = cx - cy
    #                 diffyx = cy - cx
    #
    #                 if len(diffxy) == 1:
    #                     codigo = diffxy.pop()
    #                     equipo = (ex - ey).pop()
    #                     self.equipo2codigo[equipo] = codigo
    #                     (self.codigo2equipo[codigo]).add(equipo)
    #                     cambioClavesConjuntos = True
    #                     cambios = True
    #                 elif len(diffxy) == 0:
    #                     pass  # Nada que hacer
    #                 else:
    #                     pass  # TODO: Pensar
    #
    #                 if len(diffyx) == 1:
    #                     codigo = diffyx.pop()
    #                     equipo = (ey - ex).pop()
    #                     self.equipo2codigo[equipo] = codigo
    #                     (self.codigo2equipo[codigo]).add(equipo)
    #                     cambioClavesConjuntos = True
    #                     cambios = True
    #                 elif len(diffyx) == 0:
    #                     pass  # Nada que hacer
    #                 else:
    #                     pass  # TODO: Pensar


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

import re
from collections import defaultdict
from copy import deepcopy
from itertools import combinations
from time import gmtime, strptime

import bs4

from SMACB.PartidoACB import GeneraURLpartido
from Utils.Misc import CompareBagsOfWords, PARSERfechaC
from Utils.Web import ComposeURL, DescargaPagina, ExtraeGetParams, MergeURL

URL_BASE = "http://www.acb.com"

calendario_URLBASE = "http://acb.com/calendario.php"
template_URLFICHA = "http://www.acb.com/fichas/%s%i%03i.php"
UMBRALbusquedaDistancia = 1  # La comparación debe ser >


class CalendarioACB(object):

    def __init__(self, urlbase=calendario_URLBASE, **kwargs):
        self.timestamp = gmtime()
        self.competicion = kwargs.get('competicion', "LACB")
        self.nombresCompeticion = defaultdict(int)
        self.edicion = kwargs.get('edicion')
        self.Partidos = {}
        self.Jornadas = {}
        self.equipo2codigo = {}
        self.codigo2equipo = defaultdict(set)
        self.url = urlbase

    def actualizaCalendario(self, home=None, browser=None, config={}):
        calendarioPage = self.descargaCalendario(home=home, browser=browser, config=config)
        self.procesaCalendario(calendarioPage)
        calendarioPage['browser'].close()

    def procesaCalendario(self, content):
        if 'timestamp' in content:
            self.timestamp = content['timestamp']
        if 'source' in content:
            self.url = content['source']
        calendarioData = content['data']

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

                    jornadaMatch = re.match(r"JORNADA\s+(\d+)", tituloFields[1])
                    if jornadaMatch:  # Liga Endesa 2017-18 - JORNADA 34
                        currJornada = int(jornadaMatch.groups()[0])
                        self.Jornadas[currJornada] = dict()
                        self.Jornadas[currJornada]['nombre'] = tituloFields[1]
                        self.Jornadas[currJornada]['partidos'] = []
                        self.Jornadas[currJornada]['pendientes'] = []
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
                    self.procesaSelectorClubes(item)
                elif ('tablajornadas' in divClasses):  # Selector para calendario de clubes
                    if tablaPlayoffs:
                        self.procesaTablaCalendarioJornadas(item)
                    else:
                        continue
                else:
                    print("DIV Unprocessed: ", item.attrs)
            elif item.name == 'table':
                self.procesaTablaJornada(item, currJornada)
            elif item.name in ('br'):  # Otras cosas que no interesan
                continue
            else:
                print("Unexpected: ", item, item.__dict__.keys())

        # Detecta los cambios de nombre de equipo
        self.gestionaNombresDeEquipo()

        for jornada in self.Jornadas:
            if not self.Jornadas[jornada]['partidos']:
                continue

            for partido in self.Jornadas[jornada]['partidos']:
                self.Partidos[partido]['esPlayoff'] = self.Jornadas[jornada]['esPlayoff']
                codigos = [self.equipo2codigo.get(x, None) for x in self.Partidos[partido]['equipos']]
                if None in codigos:
                    raise BaseException("Equipo sin codigo en '%s' (%s) " %
                                        (" - ".join(self.Partidos[partido]['equipos']), partido))
                self.Partidos[partido]['codigos'] = codigos

    def procesaTablaJornada(self, tagTabla, currJornada):
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
                puntos = [int(x.strip()) for x in cols[2].string.split(" - ")]

                paramsURL = ExtraeGetParams(linkGame['href'])
                self.Partidos[linkOk] = {'url': linkOk, 'URLparams': paramsURL, 'jornada': currJornada,
                                         'equipos': equipos, 'resultado': puntos}
                (self.Jornadas[currJornada]['partidos']).append(linkOk)
            else:  # No ha habido partido
                partidoPendiente = dict()
                partidoPendiente['jornada'] = currJornada
                partidoPendiente['equipos'] = equipos
                textoFecha = cols[2].string
                if textoFecha:
                    try:
                        fechaPart = strptime(textoFecha, PARSERfechaC)
                        partidoPendiente['fecha'] = fechaPart
                    except ValueError:
                        partidoPendiente['fecha'] = None
                else:
                    partidoPendiente['fecha'] = None

                self.Jornadas[currJornada]['pendientes'].append(partidoPendiente)

    def procesaSelectorClubes(self, tagForm):
        optionList = tagForm.find_all("option")
        for optionTeam in optionList:
            equipoCodigo = optionTeam['value']
            equipoNombre = optionTeam.string
            if equipoCodigo == "0":
                continue
            self.nuevaTraduccionEquipo2Codigo(equipoNombre, equipoCodigo)

    def procesaTablaCalendarioJornadas(self, tagTabla):
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

    def gestionaNombresDeEquipo(self):
        """ Intenta tener en cuenta los nombres de equipos que cambian a lo largo de la temporada (patrocinios)
        """

        def cods2key(cset):
            return "|".join(sorted(list(cset)))

        def purgaSets(obj, pair):
            cods, noms = deepcopy(pair)

            changes = True
            while changes:
                changes = False
                if len(cods) == 1 and len(noms) == 1:
                    cod = cods.pop()
                    nom = noms.pop()
                    print("PS: Encontrada comb %s -> %s" % (nom, cod))
                    obj.nuevaTraduccionEquipo2Codigo(nom, cod)
                    changes = True

                auxNoms = deepcopy(noms)
                for nom in auxNoms:
                    if nom in obj.equipo2codigo:
                        cod = obj.equipo2codigo[nom]
                        if cod not in cods:
                            raise ValueError(
                                "purgaSets: traduccion '%s' para '%s' no está en códigos disponibles %s en %s" % (
                                    cod, nom, cods, pair))
                        noms.remove(nom)
                        cods.remove(cod)
                        changes = True

            return (cods, noms)

        codigosTemporada = set(self.codigo2equipo.keys())
        combinacionesNoUsadas = defaultdict(set)

        #Repasa todas las jornadas (hacia atrás) asignando los codigos a los equipos a partir de la lista del calendario
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

            if len(codigosNoUsados) == 1 and len(equiposNoAsignados) == 1:
                codigo = codigosNoUsados.pop()
                equipo = equiposNoAsignados.pop()
                self.nuevaTraduccionEquipo2Codigo(equipo, codigo)

            #Trata de buscar en los nombres no asignados por similitud de palabras
            auxEquiposNoAsignados = deepcopy(equiposNoAsignados)
            for equipo in auxEquiposNoAsignados:
                auxCodigosNoUsados = deepcopy(codigosNoUsados)
                codigo = self.buscaEquipo2CodigoDistancia(equipo, codigosObjetivo=auxCodigosNoUsados)
                if codigo:
                    self.nuevaTraduccionEquipo2Codigo(equipo, codigo)
                    equiposNoAsignados.remove(equipo)
                    codigosNoUsados.remove(codigo)

            if not equiposNoAsignados:  # Se asignado todo!
                continue

            #No hay manera, a la busqueda final
            if codigosNoUsados:
                combinacionesNoUsadas[cods2key(codigosNoUsados)].add(cods2key(equiposNoAsignados))

        if not combinacionesNoUsadas:
            return

        # De todos los grupos (codigos sin asignar y nombres sin asignar). Los compara para ver si saca algo.
        changes = True
        while changes:
            changes = False

            conjs = []

            for k, nomslist in list(combinacionesNoUsadas.items()):
                cods = k.split("|")


                for v in deepcopy(nomslist):
                    noms = v.split("|")

                    #Elimina el caso trivial 1 codigo = 1 nombre. No debería haber llegado aquí pero...
                    if len(cods) == 1 and len(noms) == 1:
                        nom = noms.pop()
                        cod = cods[0]
                        print("Encontrada comb %s -> %s" % (nom, cod))
                        self.nuevaTraduccionEquipo2Codigo(nom, cod)
                        combinacionesNoUsadas[k].remove(v)
                        if len(combinacionesNoUsadas[k]) == 0:
                            del combinacionesNoUsadas[k]
                        changes = True
                        continue

                    conjs.append((set(cods), set(noms)))

            # Para cada par de grupos no asignados los compara entre sí e intenta aplicar alguna lógica
            for c1, c2 in combinations(conjs, 2):
                if c1 == c2:
                    continue

                # Lo que queda del grupo c1 si le quitas lo que ya se sabe
                cods1, noms1 = purgaSets(self, deepcopy(c1))
                if c1[0] != cods1 and c1[1] != noms1:
                    kc = cods2key(c1[0])
                    kv = cods2key(c1[1])
                    if kv in combinacionesNoUsadas[kc]:
                        combinacionesNoUsadas[kc].remove(kv)
                    if len(combinacionesNoUsadas[kc]) == 0:
                        del combinacionesNoUsadas[kc]
                    changes = True

                # Lo que queda del grupo c2 si le quitas lo que ya se sabe
                cods2, noms2 = purgaSets(self, deepcopy(c2))
                if c2[0] != cods1 and c2[1] != noms2:
                    kc = cods2key(c2[0])
                    kv = cods2key(c2[1])
                    if kv in combinacionesNoUsadas[kc]:
                        combinacionesNoUsadas[kc].remove(kv)
                    if len(combinacionesNoUsadas[kc]) == 0:
                        del combinacionesNoUsadas[kc]
                    changes = True

                # Si de alguno de los grupos ya se conocian todas las asignaciones no nos vale pero puede habre creado
                # alguno nuevo
                if len(cods1) == 0 or len(cods2) == 0 or len(noms1) == 0 or len(noms2) == 0:
                    if len(cods1) > 0 and len(noms1) > 0:
                        combinacionesNoUsadas[cods2key(cods1)].add(cods2key(noms1))
                        changes = True

                    if len(cods2) > 0 and len(noms2) > 0:
                        combinacionesNoUsadas[cods2key(cods2)].add(cods2key(noms2))
                        changes = True

                    continue

                # Calcula la intersección entre los grupos. Si nos sale alguno de len 1, ya tenemos asignación
                intC12 = cods1.intersection(cods2)
                intN12 = noms1.intersection(noms2)

                if len(intC12) == 1 and len(intN12) == 1:
                    cod = intC12.pop()
                    nom = intN12.pop()
                    print("Encontrada comb %s -> %s" % (nom, cod))
                    self.nuevaTraduccionEquipo2Codigo(nom, cod)
                    changes = True

                    newC = set()
                    newC.add(cod)

                    newN = set()
                    newN.add(nom)

                    newC1 = cods1 - newC
                    newC2 = cods2 - newC
                    newN1 = noms1 - newN
                    newN2 = noms2 - newN

                    # Y creamos grupos nuevos con lo que queda de quitar lo aprendido nuevo
                    if len(newC1) > 0 and len(newN1) > 0:
                        combinacionesNoUsadas[cods2key(newC1)].add(cods2key(newN1))

                    if len(newC2) > 0 and len(newN2) > 0:
                        combinacionesNoUsadas[cods2key(newC2)].add(cods2key(newN2))

        # Por combinatoria ya no sale nada, toca comparar con los calendarios existentes
        changes = True
        while changes:
            changes = False
            for k, nomslist in list(combinacionesNoUsadas.items()):
                cods = k.split("|")

                for v in nomslist:
                    noms = v.split("|")
                    origPair = (set(cods), set(noms))
                    pCod, pNom = purgaSets(self, origPair)

                    # Un ultimo intento de quitar cosas conocidas
                    if len(pCod) == 0 or len(pNom) == 0:
                        continue
                    elif len(pCod) == 1 or len(pNom) == 1:
                        cod = pCod.pop()
                        nom = pNom.pop()
                        print("Encontrada comb %s -> %s" % (nom, cod))
                        self.nuevaTraduccionEquipo2Codigo(nom, cod)
                        changes = True
                        continue

                    # se acabó, toca descargar el calendario completo del club y buscar los nombres más frecuentes no
                    # conocidos
                    for cod in pCod:
                        calEQ = self.descargaCalendarioEquipo(codEquipo=cod)
                        calProc = self.procesaCalendarioEquipo(calEQ)
                        if len(calProc) == 1:
                            newNom = list(calProc.keys())[0]
                            self.nuevaTraduccionEquipo2Codigo(newNom, cod)
                            print("Encontrada comb %s -> %s" % (newNom, cod))
                            changes = True
                            continue

                        calPurged = {k: v for k, v in calProc.items() if v >= 2}
                        if len(calPurged) == 1:
                            newNom = list(calPurged.keys())[0]
                            self.nuevaTraduccionEquipo2Codigo(newNom, cod)
                            print("Encontrada comb %s -> %s" % (newNom, cod))
                            changes = True
                            continue

    def buscaEquipo2CodigoDistancia(self, equipoAbuscar, codigosObjetivo=None):
        if equipoAbuscar in self.equipo2codigo:
            return self.equipo2codigo[equipoAbuscar]

        if codigosObjetivo:
            listaCodigos = codigosObjetivo
        else:
            listaCodigos = self.codigo2equipo.keys()

        distancias = []
        for codigo in listaCodigos:
            for nombreObj in list(self.codigo2equipo[codigo]):
                tupla = (nombreObj, codigo, CompareBagsOfWords(equipoAbuscar, nombreObj))
                if tupla[2] > UMBRALbusquedaDistancia:
                    distancias.append(tupla)

        if distancias:
            resultados = sorted(distancias, key=lambda x: x[2], reverse=True)
            codigoResultado = resultados[0][1]

            self.nuevaTraduccionEquipo2Codigo(equipoAbuscar, codigoResultado)
            return codigoResultado
        else:
            print("No se han encontrado códigos posibles: %s" % equipoAbuscar)
            # TODO: Esto debería ser una excepción
            return None

    def nuevaTraduccionEquipo2Codigo(self, equipo, codigo):
        if equipo in self.equipo2codigo:
            return False

        self.equipo2codigo[equipo] = codigo
        (self.codigo2equipo[codigo]).add(equipo)
        return True

    def nombresJornada(self):
        result = [self.Jornadas[x]['nombre'].replace('JORNADA ', 'J ').replace(" P.", "").replace(",", "")
                  for x in self.Jornadas]

        return result

    def descargaCalendario(self, home=None, browser=None, config={}):
        urlCalendario = ComposeURL(self.url,
                                   {'cod_competicion': self.competicion, 'cod_edicion': self.edicion, 'vd': "1",
                                    'vh': "60"})
        calendarioPage = DescargaPagina(urlCalendario, home=home, browser=browser, config=config)

        return calendarioPage

    def descargaCalendarioEquipo(self, codEquipo, home=None, browser=None, config={}):
        calWrk = self.descargaCalendario(home=home, browser=browser, config=config)

        # Mira si el equipo es válido
        pagWrk = calWrk['data']

        divWrk = pagWrk.find('div', attrs={'class': 'cuerponaranja'})
        frmWrk = divWrk.find('form')

        opts = dict()
        for opt in frmWrk.findAll('option'):
            opttxt = opt.get_text()
            if opttxt == '':
                continue
            optval = opt['value']
            opts[optval] = opttxt
        if codEquipo not in opts:
            raise KeyError("descargaCalendarioEquipo: '%s' no está en la edición %s. Equipos disponibles: %s" % (
                codEquipo, self.edicion, ", ".join(opts)))

        # Descarga calendario
        browserWrk = calWrk['browser']

        browserWrk.select_form('form[action="partclub.php"]')
        browserWrk['cod_equipo'] = codEquipo

        result = browserWrk.submit_selected()
        if not result.ok:
            raise ValueError("descargaCalendarioEquipo: problemas descargando calendario para '%s'. %s: %s" % (
                codEquipo, result.status_code, result.content))

        source = browserWrk.get_url()
        content = browserWrk.get_current_page()

        return {'source': source, 'data': content, 'timestamp': gmtime(), 'home': home, 'browser': browserWrk,
                'config': config}

    def procesaCalendarioEquipo(self, calEquipo):
        tableCal = calEquipo['data'].find('table', attrs={'class': 'resultados'})

        eqNames = defaultdict(int)
        for part in tableCal.findAll('tr'):
            tdPart = part.find('td', attrs={'class': 'naranjaclaro2'})
            if tdPart is None:
                continue
            partTxt = tdPart.get_text()
            partEqs = partTxt.split(' - ')
            for equipo in partEqs:
                eqName = equipo.strip()
                if eqName in self.equipo2codigo:
                    continue
                eqNames[eqName] += 1

        return eqNames


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

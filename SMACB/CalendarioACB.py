import re
from argparse import Namespace
from collections import defaultdict
from copy import deepcopy
from itertools import combinations
from time import gmtime, strptime

from Utils.Misc import CompareBagsOfWords, FORMATOtimestamp
from Utils.Web import DescargaPagina, MergeURL, getObjID
from .SMconstants import URL_BASE

calendario_URLBASE = "http://www.acb.com/calendario"
template_URLFICHA = "http://www.acb.com/fichas/%s%i%03i.php"
# http://www.acb.com/calendario/index/temporada_id/2018
# http://www.acb.com/calendario/index/temporada_id/2019/edicion_id/952
template_CALENDARIOYEAR = "http://www.acb.com/calendario/index/temporada_id/{year}"
template_CALENDARIOFULL = "http://www.acb.com/calendario/index/temporada_id/{year}/edicion_id/{compoID}"

UMBRALbusquedaDistancia = 1  # La comparación debe ser >


class CalendarioACB(object):

    def __init__(self, urlbase=calendario_URLBASE, **kwargs):
        self.timestamp = gmtime()
        self.competicion = kwargs.get('competicion', "LACB")
        self.nombresCompeticion = defaultdict(int)
        self.edicion = kwargs.get('edicion')
        self.Partidos = {}
        self.Jornadas = {}
        self.eq2codigo = {}
        self.codigo2eq = defaultdict(set)
        self.urlbase = urlbase
        self.url = None

    def actualizaCalendario(self, home=None, browser=None, config=Namespace()):
        calendarioPage = self.descargaCalendario(home=home, browser=browser, config=config)

        return self.procesaCalendario(calendarioPage)  # CAP:

    def procesaCalendario(self, content):
        if 'timestamp' in content:
            self.timestamp = content['timestamp']
        if 'source' in content:
            self.url = content['source']
        calendarioData = content['data']

        for divJ in calendarioData.find_all("div", {"class": "cabecera_jornada"}):
            datosCab = procesaCab(divJ)

            currJornada = int(datosCab['jornada'])

            divPartidos = divJ.find_next_sibling("div", {"class": "listado_partidos"})

            self.Jornadas[currJornada] = self.procesaBloqueJornada(divPartidos, datosCab)

        return content  # CAP

    # def procesaTablaJornada(self, tagTabla, currJornada):
    #     for row in tagTabla.find_all("tr"):
    #         cols = row.find_all("td", recursive=False)
    #
    #         equipos = [x.strip() for x in cols[1].string.split(" - ")]
    #         for equipo in equipos:
    #             (self.Jornadas[currJornada]['equipos']).add(equipo)
    #
    #         # si el partido ha sucedido, hay un enlace a las estadisticas en la col 0 (tambien en la del resultado)
    #         linksCol0 = cols[0].find_all("a")
    #
    #         if linksCol0:
    #             linkGame = linksCol0[0]
    #             linkOk = GeneraURLpartido(linkGame)
    #             puntos = [int(x.strip()) for x in cols[2].string.split(" - ")]
    #
    #             paramsURL = ExtraeGetParams(linkGame['href'])
    #             self.Partidos[linkOk] = {'url': linkOk, 'URLparams': paramsURL, 'jornada': currJornada,
    #                                      'equipos': equipos, 'resultado': puntos}
    #             (self.Jornadas[currJornada]['partidos']).append(linkOk)
    #         else:  # No ha habido partido
    #             partidoPendiente = dict()
    #             partidoPendiente['jornada'] = currJornada
    #             partidoPendiente['equipos'] = equipos
    #             textoFecha = cols[2].string
    #             if textoFecha:
    #                 try:
    #                     fechaPart = strptime(textoFecha, PARSERfechaC)
    #                     partidoPendiente['fecha'] = fechaPart
    #                 except ValueError:
    #                     partidoPendiente['fecha'] = None
    #             else:
    #                 partidoPendiente['fecha'] = None
    #
    #             self.Jornadas[currJornada]['pendientes'].append(partidoPendiente)
    #

    def procesaSelectorClubes(self, tagForm):
        optionList = tagForm.find_all("option")
        for optionTeam in optionList:
            equipoCodigo = optionTeam['value']
            equipoNombre = optionTeam.string
            if equipoCodigo == "0":
                continue
            self.nuevaTraduccionEquipo2Codigo(equipoNombre, equipoCodigo)

    # def procesaTablaCalendarioJornadas(self, tagTabla):
    #     for table in tagTabla.find_all("table", attrs={'class': 'jornadas'}):
    #         for row in table.find_all("tr"):
    #             cols = row.find_all("td", recursive=False)
    #             if len(cols) == 2:  # Encabezamiento tabla
    #                 continue
    #             currJornada = int(cols[1].string)
    #             if currJornada not in self.Jornadas:
    #                 self.Jornadas[currJornada] = dict()
    #                 self.Jornadas[currJornada]['partidos'] = []
    #                 self.Jornadas[currJornada]['equipos'] = set()
    #
    #             tituloFields = cols[2].string.split(":")
    #             self.Jornadas[currJornada]['nombre'] = tituloFields[0].strip()
    #             self.Jornadas[currJornada]['esPlayoff'] = True

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

        codigosTemporada = set(self.codigo2eq.keys())
        combinacionesNoUsadas = defaultdict(set)

        # Repasa todas las jornadas (y pasadas) asignando los codigos a los equipos a partir de la lista del calendario
        for jornada in sorted(self.Jornadas.keys(), reverse=True):
            if self.Jornadas[jornada]['esPlayoff']:
                continue

            if not self.Jornadas[jornada]['equipos']:
                continue

            codigosUsados = set()
            equiposNoAsignados = set()

            for equipo in self.Jornadas[jornada]['equipos']:
                if equipo in self.eq2codigo:
                    codigosUsados.add(self.eq2codigo[equipo])
                else:
                    equiposNoAsignados.add(equipo)
            codigosNoUsados = codigosTemporada - codigosUsados

            if not equiposNoAsignados:  # Se asignado todo!
                continue

            if len(codigosNoUsados) == 1 and len(equiposNoAsignados) == 1:
                codigo = codigosNoUsados.pop()
                equipo = equiposNoAsignados.pop()
                self.nuevaTraduccionEquipo2Codigo(equipo, codigo)

            # Trata de buscar en los nombres no asignados por similitud de palabras
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

            # No hay manera, a la busqueda final
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

                    # Elimina el caso trivial 1 codigo = 1 nombre. No debería haber llegado aquí pero...
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
        if equipoAbuscar in self.eq2codigo:
            return self.eq2codigo[equipoAbuscar]

        if codigosObjetivo:
            listaCodigos = codigosObjetivo
        else:
            listaCodigos = self.codigo2eq.keys()

        distancias = []
        for codigo in listaCodigos:
            for nombreObj in list(self.codigo2eq[codigo]):
                tupla = (nombreObj, codigo, CompareBagsOfWords(equipoAbuscar, nombreObj))
                if tupla[2] > UMBRALbusquedaDistancia:
                    distancias.append(tupla)

        if distancias:
            resultados = sorted(distancias, key=lambda x: x[2], reverse=True)
            codigoResultado = resultados[0][1]

            self.nuevaTraduccionEquipo2Codigo(equipoAbuscar, codigoResultado)
            return codigoResultado
        else:

            print("No se han encontrado códigos posibles: %s (%s:%s)" % (equipoAbuscar, codigosObjetivo, listaCodigos))
            # TODO: Esto debería ser una excepción
            return None

    def nuevaTraduccionEquipo2Codigo(self, equipo, codigo):
        if equipo in self.eq2codigo:
            return False

        self.eq2codigo[equipo] = codigo
        (self.codigo2eq[codigo]).add(equipo)
        return True

    def nombresJornada(self):
        result = [self.Jornadas[x]['nombre'].replace('JORNADA ', 'J ').replace(" P.", "").replace(",", "")
                  for x in self.Jornadas]

        return result

    def descargaCalendario(self, home=None, browser=None, config=Namespace()):
        if self.url is None:
            pagCalendario = DescargaPagina(self.urlbase, home=home, browser=browser, config=config)
            pagCalendarioData = pagCalendario['data']
            divTemporadas = pagCalendarioData.find("div", {"class": "listado_temporada"})

            currYear = divTemporadas.find('div', {"class": "elemento"})['data-t2v-id']

            urlYear = template_CALENDARIOYEAR.format(year=self.edicion)
            if self.edicion is None:
                self.edicion = currYear
                pagYear = pagCalendario
            else:
                listaTemporadas = {x['data-t2v-id']: x.get_text() for x in
                                   divTemporadas.find_all('div', {"class": "elemento"})}
                if self.edicion not in listaTemporadas:
                    raise KeyError("Temporada solicitada {year} no está entre las disponibles ({listaYears})".format(
                        year=self.edicion, listaYears=", ".join(listaTemporadas.keys())))

                pagYear = DescargaPagina(urlYear, home=None, browser=browser, config=config)

            pagYearData = pagYear['data']

            divCompos = pagYearData.find("div", {"class": "listado_competicion"})
            listaCompos = {x['data-t2v-id']: x.get_text() for x in divCompos.find_all('div', {"class": "elemento"})}
            compoClaves = compo2clave(listaCompos)

            priCompoID = divCompos.find('div', {"class": "elemento"})['data-t2v-id']

            if self.competicion not in compoClaves:
                listaComposTxt = ["{k} = '{label}'".format(k=x, label=listaCompos[compoClaves[x]]) for x in
                                  compoClaves]
                raise KeyError("Compo solicitada {compo} no disponible. Disponibles: {listaCompos}".format(
                    compo=self.competicion, listaCompos=", ".join(listaComposTxt)))

            self.url = template_CALENDARIOFULL.format(year=self.edicion, compoID=compoClaves[self.competicion])

            if compoClaves[self.competicion] == priCompoID:
                result = pagYear
            else:
                result = DescargaPagina(self.url, browser=browser, home=None, config=config)
        else:
            result = DescargaPagina(self.url, browser=browser, home=None, config=config)

        return result

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
                if eqName in self.eq2codigo:
                    continue
                eqNames[eqName] += 1

        return eqNames

    def procesaBloqueJornada(self, divDatos, dictCab):
        # TODO: incluir datos de competicion
        result = dict()
        result['nombre'] = dictCab['comp']
        result['jornada'] = int(dictCab['jornada'])
        result['partidos'] = []
        result['pendientes'] = []
        result['equipos'] = set()
        result['esPlayoff'] = None

        # print(divPartidos)
        for artP in divDatos.find_all("article", {"class": "partido"}):
            datosPart = self.procesaBloquePartido(dictCab, artP)
            if datosPart['pendiente']:
                result['pendientes'].append(datosPart)
            else:
                self.Partidos[datosPart['url']] = datosPart
                result['partidos'].append(datosPart)

        return result

    def procesaBloquePartido(self, datosJornada, divPartido):
        # TODO: incluir datos de competicion
        resultado = dict()
        resultado['pendiente'] = True
        resultado['fecha'] = None
        resultado['jornada'] = datosJornada['jornada']

        resultado['cod_competicion'] = self.competicion
        resultado['cod_edicion'] = self.edicion

        datosPartEqs = dict()
        for eqUbic in ['local', 'visitante']:
            divsEq = divPartido.find_all("div", {"class": eqUbic})
            infoEq = procesaDivsEquipo(divsEq)
            datosPartEqs[eqUbic.capitalize()] = infoEq
            self.codigo2eq[infoEq['abrev']].add(infoEq['nomblargo'])
            self.codigo2eq[infoEq['abrev']].add(infoEq['nombcorto'])
            self.eq2codigo[infoEq['nomblargo']] = infoEq['abrev']
            self.eq2codigo[infoEq['nombcorto']] = infoEq['abrev']

        resultado['equipos'] = datosPartEqs

        if 'enlace' in datosPartEqs['Local']:
            resultado['pendiente'] = False
            linkGame = datosPartEqs['Local']['enlace']
            resultado['url'] = MergeURL(self.url, linkGame)
            resultado['resultado'] = {x: datosPartEqs[x]['puntos'] for x in datosPartEqs}
            resultado['codigos'] = {x: datosPartEqs[x]['abrev'] for x in datosPartEqs}
            resultado['partido'] = getObjID(linkGame)

        else:
            divTiempo = divPartido.find('div', {"class": "info"})

            if divTiempo:
                cadFecha = divTiempo.find('span', {"class": "fecha"}).next.lower()
                cadHora = divTiempo.find('span', {"class": "hora"}).get_text()

                resultado['fecha'] = procesaFechaHoraPartido(cadFecha.strip(), cadHora.strip(), datosJornada)

        return resultado


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
            raise SystemError("Too many or none links to Calendario. {}".format(callinks))

    result = MergeURL(url, link['href'])

    return result


def compo2clave(listaCompos):
    """
    Dado un diccionario con lo que aparece en el desplegable (id -> nombre compo), devuelve otro con las claves
    tradicionales (pre verano 2019)
    :param listaCompos:
    :return:
    """
    result = dict()

    for id, label in listaCompos.items():
        if 'liga' in label.lower():
            result['LACB'] = id
        elif 'supercopa' in label.lower():
            result['SCOPA'] = id
        elif 'copa' in label.lower():
            result['COPA'] = id

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

    patronL = r'(?P<comp>.*) (?P<yini>\d{4})-(?P<yfin>\d{4}) - JORNADA (?P<jornada>\d+)'

    patL = re.match(patronL, cadL)

    resultado.update(patL.groupdict())

    resultado['auxFechas'] = procesaFechasJornada(cadR)

    return resultado


def procesaFechasJornada(cadFechas):
    resultado = dict()

    mes2n = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10,
             'nov': 11, 'dic': 12}

    patronBloqueFechas = r'^(?P<dias>\d{1,2}(-\d{1,2})*)\s+(?P<mes>\w+)\s+(?P<year>\d{4})$'

    cadWrk = cadFechas.lower().strip()
    bloques = cadWrk.split(" y ")

    for b in bloques:
        reFecha = re.match(patronBloqueFechas, b.strip())
        if reFecha:
            yearN = int(reFecha['year'].strip())
            for d in reFecha['dias'].split("-"):
                diaN = int(d.strip())
                cadResult = "%04i-%02i-%02i" % (yearN, mes2n[reFecha['mes']], diaN)
                if diaN in resultado:
                    resultado[diaN].add(cadResult)
                else:
                    resultado[diaN] = {cadResult}
        else:
            raise ValueError("RE: '%s' no casa patrón '%s'" % (b, patronBloqueFechas))

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
            raise ValueError("procesaDivsEquipo: CASO NO TRATADO: %s" % str(d))

    return resultado


def procesaFechaHoraPartido(cadFecha, cadHora, datosCab):
    resultado = None
    diaSem2n = {'lun': 0, 'mar': 1, 'mié': 2, 'jue': 3, 'vie': 4, 'sáb': 5, 'dom': 6}
    patronDiaPartido = r'^(?P<diasem>\w+)\s(?P<diames>\d{1,2})$'

    reFechaPart = re.match(patronDiaPartido, cadFecha.strip())

    if reFechaPart:
        diaSemN = diaSem2n[reFechaPart['diasem']]
        diaMesN = int(reFechaPart['diames'])

        auxFechasN = deepcopy(datosCab['auxFechas'])[diaMesN]

        if len(auxFechasN) > 1:
            # TODO Magic para procesar dias repetidos (cuando suceda)
            pass
        else:
            cadFechaFin = auxFechasN.pop()
            cadMezclada = "%s %s" % (cadFechaFin.strip(), cadHora.strip())
            try:
                fechaPart = strptime(cadMezclada, FORMATOtimestamp)
                resultado = fechaPart
            except ValueError:
                print("procesaFechaHoraPartido: '%s' no casa RE '%s'" % (cadFechaFin, FORMATOtimestamp))
                resultado = None
    else:
        raise ValueError("RE: '%s' no casa patrón '%s'" % (cadFecha, patronDiaPartido))

    return resultado

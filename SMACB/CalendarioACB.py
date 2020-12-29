import re
from argparse import Namespace
from collections import defaultdict
from copy import deepcopy

import pandas as pd
from time import gmtime

from Utils.FechaHora import NEVER
from Utils.Misc import FORMATOtimestamp
from Utils.Web import DescargaPagina, getObjID, MergeURL
from .SMconstants import URL_BASE

calendario_URLBASE = "http://www.acb.com/calendario"
template_URLFICHA = "http://www.acb.com/fichas/%s%i%03i.php"
# http://www.acb.com/calendario/index/temporada_id/2018
# http://www.acb.com/calendario/index/temporada_id/2019/edicion_id/952
template_CALENDARIOYEAR = "http://www.acb.com/calendario/index/temporada_id/{year}"
template_CALENDARIOFULL = "http://www.acb.com/calendario/index/temporada_id/{year}/edicion_id/{compoID}"

ETIQubiq = ['local', 'visitante']

UMBRALbusquedaDistancia = 1  # La comparación debe ser >

PARTIDOSnever = []
CALENDARIOEQUIPOS = dict()


class CalendarioACB(object):

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

    def nuevaTraduccionEquipo2Codigo(self, equipos, codigo, id=None):
        result = False
        eqList = equipos if isinstance(equipos, (list, set, tuple)) else [equipos]

        for eqName in eqList:
            if (eqName not in self.tradEquipos['n2c']) or (codigo not in self.tradEquipos['c2n']):
                result = True
            self.tradEquipos['n2c'][eqName].add(codigo)
            (self.tradEquipos['c2n'][codigo]).add(eqName)

            if id is not None:
                if (id not in self.tradEquipos['i2c']) or (id not in self.tradEquipos['i2n']) or (
                        eqName not in self.tradEquipos['n2i']) or (codigo not in self.tradEquipos['c2i']):
                    result = True
                self.tradEquipos['i2c'][id].add(codigo)
                (self.tradEquipos['c2i'][codigo]).add(id)
                self.tradEquipos['n2i'][eqName].add(id)
                (self.tradEquipos['i2n'][id]).add(eqName)

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
                if datosPart['fecha'] == NEVER:
                    print("\n procesaBloqueJornada we have a NEVER!", datosPart)
                result['pendientes'].append(datosPart)
            else:
                self.Partidos[datosPart['url']] = datosPart
                result['partidos'].append(datosPart)

        return result

    def procesaBloquePartido(self, datosJornada, divPartido):
        # TODO: incluir datos de competicion
        resultado = dict()
        resultado['pendiente'] = True
        resultado['fecha'] = NEVER
        resultado['jornada'] = datosJornada['jornada']

        resultado['cod_competicion'] = self.competicion
        resultado['cod_edicion'] = self.edicion

        datosPartEqs = dict()

        for eqUbic, div in zip(ETIQubiq, divPartido.find_all("div", {"class": "logo_equipo"})):
            auxDatos = datosPartEqs.get(eqUbic.capitalize(), {})
            image = div.find("img")
            imageURL = MergeURL(self.urlbase, image['src'])
            imageALT = image['alt']
            auxDatos.update({'icono': imageURL, 'imageTit': imageALT})
            datosPartEqs[eqUbic.capitalize()] = auxDatos

        for eqUbic in ETIQubiq:
            auxDatos = datosPartEqs.get(eqUbic.capitalize(), {})
            divsEq = divPartido.find_all("div", {"class": eqUbic})
            infoEq = procesaDivsEquipo(divsEq)
            auxDatos.update(infoEq)
            self.nuevaTraduccionEquipo2Codigo(equipos=[infoEq['nomblargo'], infoEq['nombcorto']],
                                              codigo=infoEq['abrev'], id=None)
            datosPartEqs[eqUbic.capitalize()] = auxDatos

        resultado['equipos'] = datosPartEqs
        resultado['loc2abrev'] = {x: datosPartEqs[x]['abrev'] for x in datosPartEqs}
        resultado['abrev2loc'] = {datosPartEqs[x]['abrev']: x for x in datosPartEqs}

        resultado['participantes'] = {datosPartEqs[x]['abrev'] for x in datosPartEqs}

        if 'enlace' in datosPartEqs['Local']:
            resultado['pendiente'] = False
            linkGame = datosPartEqs['Local']['enlace']
            resultado['url'] = MergeURL(self.url, linkGame)
            resultado['resultado'] = {x: datosPartEqs[x]['puntos'] for x in datosPartEqs}
            resultado['partido'] = getObjID(linkGame)

        else:
            divTiempo = divPartido.find('div', {"class": "info"})

            if divTiempo:
                auxFecha = divTiempo.find('span', {"class": "fecha"}).next
                auxHora = divTiempo.find('span', {"class": "hora"}).get_text()
                if isinstance(auxFecha, str) and auxFecha != '':
                    cadFecha = auxFecha.lower()
                    cadHora = auxHora.strip() if auxHora else None

                    resultado['fecha'] = procesaFechaHoraPartido(cadFecha.strip(), cadHora, datosJornada)
                if resultado['fecha'] == NEVER:
                    PARTIDOSnever.append(resultado)

                    print("\nCAP: procesaBloquePartido NEVER ", auxFecha, auxHora)
        return resultado

    def partidosEquipo(self, abrEq):
        targAbrevs = self.abrevsEquipo(abrEq)

        jugados = [p for p in self.Partidos.values() if
                   targAbrevs.intersection(p['participantes']) and not p['pendiente']]
        pendientes = []
        for j, dataJor in self.Jornadas.items():
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


def BuscaCalendario(url=URL_BASE, home=None, browser=None, config=None):
    if config is None:
        config = dict()
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
    resultado['nombreJornada'] = cadL
    resultado['fechasJornada'] = cadR

    patronL = r'(?P<comp>.*) (?P<yini>\d{4})-(?P<yfin>\d{4})\s+(:?-\s+(?P<extraComp>.*)\s+)?- JORNADA (?P<jornada>\d+)'

    patL = re.match(patronL, cadL)
    if patL:
        dictFound = patL.groupdict()
        # print("CAP ", dictFound)
        resultado.update(dictFound)
        resultado['auxFechas'] = procesaFechasJornada(cadR)
    else:
        raise ValueError("procesaCab: valor '%s' no casa RE '%s'", cadL, patronL)

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
                cadResult = "%04i-%02i-%02i" % (yearN, mes2n[reFecha['mes']], diaN)
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
            raise ValueError("procesaDivsEquipo: CASO NO TRATADO: %s" % str(d))

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
            print("CAP en fechas dobles", datosCab, cadFecha, cadHora)
            # TODO Magic para procesar dias repetidos (cuando suceda)
            pass
        else:
            cadFechaFin = auxFechasN.pop()
            cadMezclada = "%s %s" % (cadFechaFin.strip(), cadHora.strip())
            try:
                fechaPart = pd.to_datetime(cadMezclada)
                resultado = fechaPart
            except ValueError:
                print("procesaFechaHoraPartido: '%s' no casa RE '%s'" % (cadFechaFin, FORMATOtimestamp))
                resultado = NEVER

    else:
        raise ValueError("RE: '%s' no casa patrón '%s'" % (cadFecha, patronDiaPartido))

    return resultado

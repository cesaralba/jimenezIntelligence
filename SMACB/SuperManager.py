# -*- coding: utf-8 -*-

from collections import defaultdict
from copy import copy
from pickle import dump, load
from time import gmtime

import mechanicalsoup
import pandas as pd
from bs4 import BeautifulSoup
from mechanicalsoup import LinkNotFoundError

from SMACB.ClasifData import ClasifData
from SMACB.ManageSMDataframes import (datosLesionMerc, datosPosMerc,
                                      datosProxPartidoMerc)
from SMACB.MercadoPage import MercadoPageContent

URL_SUPERMANAGER = "http://supermanager.acb.com/index/identificar"

DFtypes = {'I-proxFuera': 'bool', 'I-activo': 'bool', 'I-lesion': 'bool', 'I-promVal': 'float64',
           'I-precio': 'int64', 'I-valJornada': 'float64', 'I-prom3Jornadas': 'float64',
           'I-sube15%': 'float64', 'I-seMantiene': 'float64', 'I-baja15%': 'float64'
           }


class BadLoginError(Exception):

    def __init__(self, url, user):
        Exception.__init__(self, "Unable to log in into '{}' as '{}'".format(url, user))


class ClosedSystemError(Exception):

    def __init__(self, url):
        Exception.__init__(self, "System '{}' is closed.".format(url))


class NoPrivateLeaguesError(Exception):

    def __init__(self, user):
        Exception.__init__(self, "User '{}' is no member of any private league.".format(user))


class SuperManagerACB(object):

    def __init__(self, ligaPrivada=None, url=URL_SUPERMANAGER):
        self.timestamp = gmtime()
        self.changed = False
        self.url = url
        self.ligaID = ligaPrivada

        self.jornadas = {}
        self.general = {}
        self.broker = {}
        self.puntos = {}
        self.rebotes = {}
        self.triples = {}
        self.asistencias = {}

        self.mercado = {}
        self.mercadoJornada = {}
        self.ultimoMercado = None

    def Connect(self, url=None, browser=None, config={}, datosACB=None):
        """ Se conecta al SuperManager con las credenciales suministradas,
            descarga el mercado y se introduce en la liga privada indicada
            o la única.
            """
        if url:
            self.url = url

        try:
            self.loginSM(browser=browser, config=config)
        except BadLoginError as logerror:
            print(logerror)
            exit(1)
        except ClosedSystemError as logerror:
            print(logerror)
            exit(1)

        # Pequeño rodeo para ver si hay mercado nuevo.
        here = browser.get_url()
        self.getMercados(browser, datosACB)
        # Vuelta al sendero
        browser.open(here)
        self.getIntoPrivateLeague(browser, config)

    def loginSM(self, browser, config):
        browser.open(self.url)

        try:
            # Fuente: https://github.com/MechanicalSoup/MechanicalSoup/blob/master/examples/expl_google.py
            browser.select_form("form[id='login']")
        except LinkNotFoundError as linkerror:
            print("loginSM: form not found: ", linkerror)
            exit(1)

        browser['email'] = config.user
        browser['clave'] = config.password
        browser.submit_selected()

        for script in browser.get_current_page().find_all("script"):
            if 'El usuario o la con' in script.get_text():
                # script.get_text().find('El usuario o la con') != -1:
                raise BadLoginError(url=self.url, user=config.user)
            elif 'El SuperManager KIA estar' in script.get_text():
                raise ClosedSystemError(url=self.url)

    def getIntoPrivateLeague(self, browser, config):
        lplink = browser.find_link(link_text='ligas privadas')
        browser.follow_link(lplink)

        ligas = extractPrivateLeagues(browser.get_current_page())

        if self.ligaID is None and len(ligas) == 1:
            targLeague = list(ligas.values())[0]
            self.ligaID = targLeague['id']
        elif self.ligaID is None and len(ligas) > 1:
            raise NoPrivateLeaguesError(config.user)
        else:
            targLeague = ligas[self.ligaID]

        browser.follow_link(targLeague['Ampliar'])

    def getJornada(self, idJornada, browser):
        pageForm = browser.get_current_page().find("form", {"id": 'FormClasificacion'})
        pageForm['action'] = "/privadas/ver/id/{}/tipo/jornada/jornada/{}".format(self.ligaID, idJornada)

        jorForm = mechanicalsoup.Form(pageForm)
        jorForm['jornada'] = str(idJornada)

        resJornada = browser.submit(jorForm, browser.get_url())
        bs4Jornada = BeautifulSoup(resJornada.content, "lxml")

        jorResults = ClasifData(label="jornada{}".format(idJornada),
                                source=browser.get_url(),
                                content=bs4Jornada)
        self.jornadas[idJornada] = jorResults
        return jorResults

    def getMercados(self, browser, datosACB=None):
        """ Descarga la hoja de mercado y la almacena si ha habido cambios """
        lastMercado = None
        newMercado = getMercado(browser, datosACB)
        newMercadoID = newMercado.timestampKey()

        if hasattr(self, "ultimoMercado"):
            if type(self.ultimoMercado) is MercadoPageContent:
                lastMercado = self.ultimoMercado
                lastMercadoID = lastMercado.timestampKey()
                self.mercado[lastMercadoID] = self.ultimoMercado
                self.ultimoMercado = lastMercadoID
            elif type(self.ultimoMercado) is str:
                lastMercadoID = self.ultimoMercado
                lastMercado = self.mercado[lastMercadoID]
                newID = lastMercado.timestampKey()
                if newID != lastMercadoID:
                    self.mercado.pop(lastMercadoID)
                    lastMercadoID = newID
                    self.mercado[lastMercadoID] = lastMercado
                    self.ultimoMercado = lastMercadoID
        else:
            if self.mercado:
                lastMercadoID = (sorted(self.mercado.keys(), reverse=True))[0]
            else:
                lastMercadoID = newMercadoID
                self.mercado[newMercadoID] = newMercado
                self.changed = True

            lastMercado = self.mercado[lastMercadoID]
            self.ultimoMercado = lastMercadoID

        if (lastMercado is None) or (newMercado != lastMercado):
            newMercadoID = newMercado.timestampKey()
            self.changed = True
            self.mercado[newMercadoID] = newMercado
            self.ultimoMercado = newMercadoID

    def addMercado(self, mercado):
        mercadoID = mercado.timestampKey()

        if (mercadoID in self.mercado) and not (mercado != self.mercado[mercadoID]):
            return

        self.mercado[mercadoID] = mercado

        if not self.ultimoMercado:
            self.ultimoMercado = mercadoID
        elif (mercado.timestamp > self.mercado[self.ultimoMercado].timestamp):
            self.ultimoMercado = mercadoID

        self.changed = True

    def getSMstatus(self, browser, config=None):

        jornadas = getJornadasJugadas(browser.get_current_page())
        if config is not None and 'jornada' in config:
            ultJornada = int(config.jornada)
            jornadasAdescargar = [ultJornada]
        elif jornadas:
            ultJornada = max(jornadas) if jornadas else 0
            jornadasAdescargar = [j for j in jornadas if j not in self.jornadas]
        else:
            return

        if jornadasAdescargar:
            self.changed = True
            # No bajes jornadas si la has puesto a mano
            if config is None or 'jornada' not in config:
                for jornada in jornadasAdescargar:
                    self.getJornada(jornada, browser)
            if ultJornada in jornadasAdescargar:
                self.general[ultJornada] = getClasif("general", browser, self.ligaID)
                self.broker[ultJornada] = getClasif("broker", browser, self.ligaID)
                self.puntos[ultJornada] = getClasif("puntos", browser, self.ligaID)
                self.rebotes[ultJornada] = getClasif("rebotes", browser, self.ligaID)
                self.triples[ultJornada] = getClasif("triples", browser, self.ligaID)
                self.asistencias[ultJornada] = getClasif("asistencias", browser, self.ligaID)
                self.mercadoJornada[ultJornada] = self.ultimoMercado

            if config is not None and 'jornada' in config:
                self.jornadas[ultJornada] = self.general[ultJornada]

    def saveData(self, filename):
        aux = copy(self)

        # Clean stuff that shouldn't be saved
        for atributo in ('changed', 'config'):
            if hasattr(aux, atributo):
                aux.__delattr__(atributo)

        # TODO: Protect this
        dump(aux, open(filename, "wb"))

    def loadData(self, filename):
        # TODO: Protect this
        aux = load(open(filename, "rb"))

        for key in aux.__dict__.keys():
            if key in ['timestamp', 'config', 'browser']:
                continue
            if key == "mercadoProg":
                self.__setattr__("ultimoMercado", aux.__getattribute__(key))
                continue
            self.__setattr__(key, aux.__getattribute__(key))

    def extraeDatosJugadoresMercado(self):

        resultado = dict()
        maxJornada = max(self.jornadas.keys())

        def listaDatos():
            return [None] * (maxJornada + 1)

        def findSubKeys(data):
            resultado = defaultdict(int)

            if type(data) is not dict:
                print("Parametro pasado no es un diccionario")
                return resultado

            for clave in data:
                valor = data[clave]
                if type(valor) is not dict:
                    print("Valor para '%s' no es un diccionario")
                    continue
                for subclave in valor.keys():
                    resultado[subclave] += 1

            return resultado

        mercadosAMirar = [None] * (maxJornada + 1)
        # ['proxFuera', 'lesion', 'cupo', 'pos', 'foto', 'nombre', 'codJugador', 'temp', 'kiaLink', 'equipo',
        # 'promVal', 'precio', 'enEquipos%', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%',
        # 'rival', 'CODequipo', 'CODrival', 'info']
        keysJugDatos = ['lesion', 'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'CODequipo']
        keysJugInfo = ['nombre', 'codJugador', 'cupo', 'pos', 'equipo', 'proxFuera', 'rival', 'activo', 'lesion',
                       'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%', 'rival',
                       'CODequipo', 'CODrival', 'info']

        for key in keysJugDatos:
            resultado[key] = defaultdict(listaDatos)
        for key in (keysJugInfo + ['activo']):
            resultado['I-' + key] = dict()

        for jornada in self.mercadoJornada:
            mercadosAMirar[jornada] = self.mercadoJornada[jornada]
        ultMercado = self.mercado[self.ultimoMercado]

        for i in range(len(mercadosAMirar)):
            mercadoID = mercadosAMirar[i]
            if not mercadoID:
                continue

            mercado = self.mercado[mercadoID]

            for jugSM in mercado.PlayerData:
                jugadorData = mercado.PlayerData[jugSM]
                codJugador = jugadorData['codJugador']

                # print("J: ",jugadorData.keys())

                for key in jugadorData:
                    if key in keysJugDatos:
                        resultado[key][codJugador][i] = jugadorData[key]
                    if key in keysJugInfo:
                        resultado['I-' + key][codJugador] = jugadorData[key]

        for jugSM in resultado['lesion']:
            resultado['I-activo'][jugSM] = (jugSM in ultMercado.PlayerData)

        return(resultado)

    def superManager2dataframe(self):
        """ Extrae un dataframe con los últimos datos de todos los jugadores que han jugado en la temporada.
        """
        DFcolNewNames = {'I-codJugador': 'codigo', 'I-cupo': 'cupo', 'I-pos': 'pos', 'I-CODrival': 'CODrival'}

        keys2remove = ['I-codJugador']
        datos = self.extraeDatosJugadoresMercado()

        targKeys = [x for x in datos.keys() if 'I-' in x]
        map(lambda x: targKeys.remove(x), keys2remove)
        dfResult = pd.DataFrame(datos, columns=targKeys)

        dfResult = dfResult.astype(DFtypes).reset_index().rename(DFcolNewNames, axis='columns')
        dfResult['pos'] = dfResult.apply(datosPosMerc, axis=1)

        tradMercado = dict()

        for claveM in dfResult.columns:
            if 'I-' in claveM:
                tradMercado[claveM] = claveM.replace("I-", "")

        dfResult = dfResult.rename(columns=tradMercado)
        dfResult['esLocal'] = ~(dfResult['proxFuera'].astype('bool'))
        dfResult['ProxPartido'] = dfResult.apply(datosProxPartidoMerc, axis=1)
        dfResult.loc[dfResult['info'].isna(), 'info'] = ""
        dfResult['infoLesion'] = dfResult.apply(datosLesionMerc, axis=1)
        dfResult.loc[~dfResult['activo'], 'ProxPartido'] = ""
        dfResult.loc[~dfResult['activo'], 'infoLesion'] = ""

        return dfResult

    def diffJornadas(self, jornada, excludeList=set()):
        result = defaultdict(dict)
        for c in ['general', 'broker', 'puntos', 'rebotes', 'asistencias', 'triples']:
            aux = self.__getattribute__(c)
            if (jornada in aux) and (jornada - 1 in aux):
                for equipo in aux[jornada].asdict():
                    result[c][equipo] = aux[jornada].data[equipo]['value'] - aux[jornada - 1].data[equipo]['value']

        if (jornada in self.jornadas):
            result['jornada'] = self.jornadas[jornada].asdict()

        return result

    def diffMercJugadores(self, jornada):
        result = dict()

        if jornada in self.mercadoJornada:
            listaMercs = list(self.mercado.keys())
            listaMercs.sort()
            jornadaIDX = listaMercs.index(self.mercadoJornada[jornada])
            mercJor = (self.mercado[listaMercs[jornadaIDX]]).PlayerData
            if jornadaIDX > 0:
                mercAnt = (self.mercado[listaMercs[jornadaIDX - 1]]).PlayerData

            for j in mercAnt:
                aux = dict()
                curPrecio = mercJor[j]['precio']
                if jornadaIDX > 0:
                    antPrecio = mercAnt[j]['precio'] if j in mercAnt else 0
                else:
                    antPrecio = 0

                for k in ['pos', 'cupo', 'lesion']:
                    aux[k] = mercAnt[j][k]
                aux['valJornada'] = mercJor[j]['valJornada']
                aux['broker'] = curPrecio - antPrecio

                result[j] = aux

        return result

class ResultadosJornadas(object):

    def __init__(self, jornada, supermanager, excludelist=set()):
        self.resultados = defaultdict(dict)
        self.valor2team = defaultdict(set)

        for team in supermanager.jornadas[jornada].data:
            if team in excludelist:
                continue
            self.resultados[team]['sm'] = supermanager.jornadas[jornada].data[team]['value']

            for comp in ['puntos', 'rebotes', 'triples', 'asistencias']:
                if jornada in supermanager.__getattribute__(comp):
                    if jornada == 1 or jornada - 1 in supermanager.__getattribute__(comp):
                        self.resultados[team][comp] = supermanager.__getattribute__(comp)[jornada].data[team]['value']
                        if jornada != 1:
                            self.resultados[team][comp] -= \
                                supermanager.__getattribute__(comp)[jornada - 1].data[team]['value']

    def puntosSM(self):
        return set([self.resultados[x]['sm'] for x in self.resultados])

    def valoresSM(self):
        result = defaultdict(list)

        for equipo in self.resultados:
            total = list()
            for clave in ['sm', 'puntos', 'rebotes', 'triples', 'asistencias']:
                if clave in self.resultados[equipo]:
                    total.append(self.resultados[equipo].get(clave))
            result[int(total[0] * 100)].append(total)

        return result


def extractPrivateLeagues(content):
    forms = content.find_all("form", {"name": "listaprivadas"})
    result = {}
    for formleague in forms:
        for privleague in formleague.find_all("tr"):
            leaguedata = {}
            inpleague = privleague.find("input", {'type': 'radio'})
            idleague = inpleague['value']
            leaguedata['id'] = idleague
            leaguedata['nombre'] = privleague.find("td", {'class': 'nombre'}).get_text()
            for lealink in privleague.find_all("a"):
                leaguedata[lealink.get_text()] = lealink['href']
            result[str(idleague)] = leaguedata

    return result


def getJornadasJugadas(content):
    result = []
    formClass = content.find("form", {"name": "FormClasificacion"})
    for jorInput in formClass.find_all("option"):
        jorNum = jorInput['value']
        if jorNum != "":
            result.append(int(jorNum))
    return result


def getClasif(categ, browser, liga):
    pageForm = browser.get_current_page().find("form", {"id": 'FormClasificacion'})
    pageForm['action'] = "/privadas/ver/id/{}/tipo/{}".format(liga, categ)

    selItem = pageForm.find("option", {'selected': 'selected'})
    jorForm = mechanicalsoup.Form(pageForm)

    if selItem:
        curJornada = selItem['value']
        jorForm['jornada'] = str(curJornada)

    resJornada = browser.submit(jorForm, browser.get_url())
    bs4Jornada = BeautifulSoup(resJornada.content, "lxml")

    jorResults = ClasifData(label=categ,
                            source=browser.get_url(),
                            content=bs4Jornada)
    return jorResults


def getMercado(browser, datosACB=None):
    browser.follow_link("mercado")
    mercadoData = MercadoPageContent({'source': browser.get_url(), 'data': browser.get_current_page()}, datosACB)
    return mercadoData

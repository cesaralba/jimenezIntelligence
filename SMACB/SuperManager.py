# -*- coding: utf-8 -*-

from copy import copy
from pickle import dump, load
from time import gmtime

import mechanicalsoup
from bs4 import BeautifulSoup
from mechanicalsoup import LinkNotFoundError

from SMACB.ClasifData import ClasifData
from SMACB.MercadoPage import MercadoPageContent

URL_SUPERMANAGER = "http://supermanager.acb.com/index/identificar"


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

    def getJornada(self, idJornada, browser, config):
        pageForm = browser.get_current_page().find("form", {"id": 'FormClasificacion'})
        pageForm['action'] = "/privadas/ver/id/{}/tipo/jornada/jornada/{}".format(config.league, idJornada)

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

        if newMercado != lastMercado:
            newMercadoID = newMercado.timestampKey()
            self.changed = True
            self.mercado[newMercadoID] = newMercado
            self.ultimoMercado = newMercadoID

    def addMercado(self, mercado):
        mercadoID = mercado.timestampKey()

        if (mercadoID in self.mercado) and not (mercado != self.mercado[mercadoID]):
            return

        self.mercado[mercadoID] = mercado

        if not self.ultimoMercado or (mercado.timestamp > self.mercado[self.ultimoMercado].timestamp):
            self.ultimoMercado = mercadoID

        self.changed = True

    def getSMstatus(self, browser, config):
        jornadas = getJornadasJugadas(browser.get_current_page())
        ultJornada = max(jornadas)
        jornadasAdescargar = [j for j in jornadas if j not in self.jornadas]
        if jornadasAdescargar:
            self.changed = True
            for jornada in jornadasAdescargar:
                self.getJornada(jornada, browser, config)
            if ultJornada in jornadasAdescargar:
                self.general[ultJornada] = getClasif("general", browser, config)
                self.broker[ultJornada] = getClasif("broker", browser, config)
                self.puntos[ultJornada] = getClasif("puntos", browser, config)
                self.rebotes[ultJornada] = getClasif("rebotes", browser, config)
                self.triples[ultJornada] = getClasif("triples", browser, config)
                self.asistencias[ultJornada] = getClasif("asistencias", browser, config)
                self.mercadoJornada[ultJornada] = self.ultimoMercado

    def saveData(self, filename):
        aux = copy(self)

        # Clean stuff that shouldn't be saved
        aux.__delattr__('changed')

        if hasattr(aux, "config"):
            aux.__delattr__("config")

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


######################################################
# Funciones extraidas de la clase SuperManagerACB
######################################################

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


def getClasif(categ, browser, config):
    pageForm = browser.get_current_page().find("form", {"id": 'FormClasificacion'})
    pageForm['action'] = "/privadas/ver/id/{}/tipo/{}".format(config.league, categ)
    curJornada = pageForm.find("option", {'selected': 'selected'})['value']

    jorForm = mechanicalsoup.Form(pageForm)
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

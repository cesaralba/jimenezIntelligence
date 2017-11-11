# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from time import gmtime
from configargparse import ArgumentParser
from mechanicalsoup import StatefulBrowser, LinkNotFoundError
from bs4 import BeautifulSoup
from babel.numbers import parse_decimal
import mechanicalsoup

# from SMACB.MercadoPage import MercadoPageContent

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

    def __init__(self, config={}, url=URL_SUPERMANAGER):
        self.timestamp = gmtime()
        self.url = url
        self.config = config
        self.browser = StatefulBrowser(soup_config={ 'features' : "html.parser"},
                           raise_on_404=True,
                           user_agent="SMparser",
                           )
        self.browser.set_verbose(self.config.verbose)
        self.jornadas = {}
        self.general = {}
        self.broker = {}
        self.puntos = {}
        self.rebotes = {}
        self.triples = {}
        self.asistencias = {}

        try:
            self.loginSM()
        except BadLoginError as logerror:
            print(logerror)
            exit(1)
        except ClosedSystemError as logerror:
            print(logerror)
            exit(1)

        self.getIntoPrivateLeague(idLeague=self.config.league)



    def loginSM(self):
        self.browser.open(self.url)

        try:
            # Fuente: https://github.com/MechanicalSoup/MechanicalSoup/blob/master/examples/expl_google.py
            self.browser.select_form("form[id='login']")
        except LinkNotFoundError as linkerror:
            print("loginSM: form not found: ", linkerror)
            exit(1)

        self.browser['email'] = self.config.user
        self.browser['clave'] = self.config.password
        self.browser.submit_selected()

        for script in self.browser.get_current_page().find_all("script"):
            if 'El usuario o la con' in script.get_text():
                # script.get_text().find('El usuario o la con') != -1:
                raise BadLoginError(url=self.url, user=self.config.user)
            elif 'El SuperManager KIA estar' in script.get_text():
                raise ClosedSystemError(url=self.url)

    def getIntoPrivateLeague(self, idLeague=None):
        lplink = self.browser.find_link(link_text='ligas privadas')
        self.browser.follow_link(lplink)

        leagues = self.extractPrivateLeagues(self.browser.get_current_page())

        if idLeague == None and len(leagues) == 1:
            targLeague = list(leagues.values())[0]
            self.config.league = targLeague['id']
        elif idLeague == None and len(leagues) > 1:
            raise NoPrivateLeaguesError(self.config.user)
        else:
            targLeague = leagues[idLeague]

        self.browser.follow_link(targLeague['Ampliar'])

    def extractPrivateLeagues(self, content):
        forms = content.find_all("form", {"name":"listaprivadas"})
        result = {}
        for formleague in forms:
            for privleague in formleague.find_all("tr"):
                leaguedata = {}
                inpleague = privleague.find("input", {'type':'radio'})
                idleague = inpleague['value']
                leaguedata['id'] = idleague
                leaguedata['nombre'] = privleague.find("td", {'class':'nombre'}).get_text()
                for lealink in privleague.find_all("a"):
                    leaguedata[lealink.get_text()] = lealink['href']
                result[str(idleague)] = leaguedata

        return result

    def getJornadasJugadas(self, content):
        result = []
        formClass = content.find("form", {"name":"FormClasificacion"})
        for jorInput in formClass.find_all("option"):
            jorNum = jorInput['value']
            if jorNum != "":
                result.append(int(jorNum))
        return result

    def getClasifData(self, content):
        result = {}
        table = content.find("table", {"class":"general"})
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            entry = {}
            entry['team'] = cells[1].get_text()
            entry['socio'] = cells[2].get_text()
            entry['value'] = parse_decimal(cells[3].get_text(), locale="de")
            result[entry['team']] = entry
        return result

    def getJornada(self, idJornada):
        pageForm = self.browser.get_current_page().find("form", {"id":'FormClasificacion'})
        pageForm['action'] = "/privadas/ver/id/{}/tipo/jornada/jornada/{}".format(self.config.league, idJornada)

        jorForm = mechanicalsoup.Form(pageForm)
        jorForm['jornada'] = str(idJornada)

        resJornada = self.browser.submit(jorForm, self.browser.get_url())
        bs4Jornada = BeautifulSoup(resJornada.content, "lxml")

        jorResults = self.getClasifData(bs4Jornada)
        self.jornadas[idJornada] = jorResults
        return jorResults

    def getClasif(self, categ):
        pageForm = self.browser.get_current_page().find("form", {"id":'FormClasificacion'})
        pageForm['action'] = "/privadas/ver/id/{}/tipo/{}".format(self.config.league, categ)
        curJornada = pageForm.find("option",{'selected':'selected'})['value']

        jorForm = mechanicalsoup.Form(pageForm)
        jorForm['jornada'] = str(curJornada)

        resJornada = self.browser.submit(jorForm, self.browser.get_url())
        bs4Jornada = BeautifulSoup(resJornada.content, "lxml")

        jorResults = self.getClasifData(bs4Jornada)
        return jorResults


    def getSMstatus(self):
        jornadas = self.getJornadasJugadas(self.browser.get_current_page())
        ultJornada = max(jornadas)
        jornadasAdescargar = [ j for j in jornadas if not j in self.jornadas ]
        if jornadasAdescargar:
            for jornada in jornadasAdescargar:
                self.getJornada(jornada)
            if ultJornada in jornadasAdescargar:
                self.getClasif("")
                self.general[ultJornada] = self.getClasif("general")
                self.broker[ultJornada] = self.getClasif("broker")
                self.puntos[ultJornada] = self.getClasif("puntos")
                self.rebotes[ultJornada] = self.getClasif("rebotes")
                self.triples[ultJornada] = self.getClasif("triples")
                self.asistencias[ultJornada] = self.getClasif("asistencias")

    def saveData(self, filename):
        pass

    def loadData(self, filename):
        pass


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add('-u', dest='user', type=str, env_var='SM_USER', required=True)
    parser.add('-p', dest='password', type=str, env_var='SM_PASSWORD', required=True)
    parser.add('-l', dest='league', type=str, env_var='SM_LEAGUE', required=False)
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    # parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()
    print(args)

    sm = SuperManagerACB(config=args)
    sm.getSMstatus()
    print(sm.asistencias,sm.broker,sm.general,sm.jornadas,sm.puntos,sm.rebotes,sm.triples)
    # sm.getIntoPrivateLeague()

    # print(sm.browser.get_current_page())


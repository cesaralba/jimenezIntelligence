# -*- coding: utf-8 -*-

from argparse import Namespace
from collections import defaultdict, Iterable
from copy import copy, deepcopy
from pickle import dump, load

import mechanicalsoup
import pandas as pd
from babel.numbers import decimal
from bs4 import BeautifulSoup
from mechanicalsoup import LinkNotFoundError
from time import gmtime

from Utils.BoWtraductor import comparaNombresPersonas, NormalizaCadena, RetocaNombreJugador
from Utils.Misc import onlySetElement
from Utils.Web import creaBrowser
from .ClasifData import ClasifData, manipulaSocio
from .Constants import bool2esp
from .LigaSM import LigaSM
from .ManageSMDataframes import datosPosMerc, datosProxPartidoMerc
from .MercadoPage import MercadoPageContent
from .PlantillaACB import descargaPlantillasCabecera

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

    def __init__(self, msg, *kargs):
        print(msg.format(*kargs))
        exit(1)


class SuperManagerACB(object):

    def __init__(self, ligasPrivadas=None, url=URL_SUPERMANAGER):
        self.timestamp = gmtime()
        self.changed = False
        self.url = url
        self.reqLigas = ligasPrivadas
        self.ligasASeguir = set()
        self.ligas = dict()

        self.mercado = {}
        self.mercadoJornada = {}
        self.ultimoMercado = None
        self.jornadasForzadas = set()

    def Connect(self, url=None, browser=None, config=Namespace(), datosACB=None):
        """ Se conecta al SuperManager con las credenciales suministradas,
            descarga el mercado y se introduce en la liga privada indicada
            o la única.
            """
        if url:
            self.url = url

        if browser is None:
            browser = creaBrowser(config)

        try:
            self.loginSM(browser=browser, config=config)
        except BadLoginError as logerror:
            print(logerror)
            exit(1)
        except ClosedSystemError as logerror:
            print(logerror)
            exit(1)

        self.actualizaTraducciones(datosACB)

        # Pequeño rodeo para ver si hay mercado nuevo.
        here = browser.get_url()
        self.getMercados(browser)
        # Vuelta al sendero

        browser.open(here)
        ligasExistentes = None

        if not self.ligasASeguir:
            ligasExistentes = self.getLigas(browser, config)
            if self.reqLigas is None:
                self.ligasASeguir = set(ligasExistentes.keys())
            else:
                self.ligasASeguir = self.reqLigas
        else:
            if self.reqLigas is not None or self.reqLigas:
                self.ligasASeguir = set(self.reqLigas)

        for lID in self.ligasASeguir:
            if lID not in self.ligas:
                if ligasExistentes is None:
                    ligasExistentes = self.getLigas(browser, config)
                self.ligas[lID] = LigaSM(id=lID, nombre=ligasExistentes[lID]['nombre'])

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

    def getLigas(self, browser, config):
        lplink = browser.find_link(link_text='ligas privadas')
        browser.follow_link(lplink)

        ligas = extractPrivateLeagues(browser.get_current_page())

        if len(ligas) == 0:
            raise NoPrivateLeaguesError("El usuario '{}' no tiene ligas privadas", config.user)

        return ligas

    def getIntoPrivateLeague(self, browser, config, lID):
        lplink = browser.find_link(link_text='ligas privadas')
        browser.follow_link(lplink)

        ligas = extractPrivateLeagues(browser.get_current_page())

        if len(ligas) == 0:
            raise NoPrivateLeaguesError("El usuario '{}' no tiene ligas privadas", config.user)
        else:
            try:
                targLeague = ligas[lID]
            except KeyError:
                raise NoPrivateLeaguesError("El usuario {} no participa en la liga privada {}", config.user, lID)

        browser.follow_link(targLeague['Ampliar'])

    def getJornada(self, ligaID, idJornada, browser):
        pageForm = browser.get_current_page().find("form", {"id": 'FormClasificacion'})
        pageForm['action'] = "/privadas/ver/id/{}/tipo/jornada/jornada/{}".format(ligaID, idJornada)

        jorForm = mechanicalsoup.Form(pageForm)
        jorForm['jornada'] = str(idJornada)

        resJornada = browser.submit(jorForm, browser.get_url())
        bs4Jornada = BeautifulSoup(resJornada.content, "lxml")

        jorResults = ClasifData(label="jornada{}".format(idJornada),
                                source=browser.get_url(),
                                content=bs4Jornada)
        return jorResults

    def getMercados(self, browser):
        """ Descarga la hoja de mercado y la almacena si ha habido cambios """
        lastMercado = None
        newMercado = self.getMercado(browser)

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
        for lID in self.ligasASeguir:
            self.getIntoPrivateLeague(browser, config, lID)
            jornadas = getJornadasJugadas(browser.get_current_page())

            estadoSM = {'jornadas': {}, 'general': {}, 'broker': {}, 'puntos': {}, 'rebotes': {}, 'triples': {},
                        'asistencias': {}}

            for j in jornadas:
                estadoSM['jornadas'][j] = self.getJornada(ligaID=lID, idJornada=j, browser=browser)

            for compo in ["general", "broker", "puntos", "rebotes", "triples", "asistencias"]:
                estadoSM[compo] = getClasif(compo, browser, lID)

            self.changed |= self.ligas[lID].nuevoEstado(estadoSM)

    def saveData(self, filename):
        aux = copy(self)
        if self.changed:
            aux.timestamp = gmtime()

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
            if key in ['config', 'browser']:
                continue
            if key == "mercadoProg":
                self.__setattr__("ultimoMercado", aux.__getattribute__(key))
                continue
            self.__setattr__(key, aux.__getattribute__(key))

    def extraeDatosJugadoresMercado(self, nombresJugadores=None, infoPlants=None):

        keysJugDatos = ['lesion', 'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'CODequipo']
        keysJugInfo = ['nombre', 'codJugador', 'cupo', 'pos', 'equipo', 'proxFuera', 'rival', 'activo', 'lesion',
                       'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%', 'rival',
                       'CODequipo', 'CODrival', 'info']

        dataPlants = descargaPlantillasCabecera(jugId2nombre=nombresJugadores) if infoPlants is None else infoPlants

        cacheLinks = dict()
        cacheEqNom = defaultdict(dict)
        codigosUsados = set()

        pendienteLinks = defaultdict(list)
        pendienteEqNom = defaultdict(lambda: defaultdict(list))

        resultado = dict()
        maxJornada = max(self.getJornadasJugadas())

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

        def actualizaResultado(resultado, codigo, jor, jugadorData):
            jugadorData['codJugador'] = codigo

            for key in jugadorData:
                if key in keysJugDatos:
                    resultado[key][codigo][jor] = jugadorData[key]
                if key in keysJugInfo:
                    resultado['I-' + key][codigo] = jugadorData[key]

        # ['proxFuera', 'lesion', 'cupo', 'pos', 'foto', 'nombre', 'codJugador', 'temp', 'kiaLink', 'equipo',
        # 'promVal', 'precio', 'enEquipos%', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%',
        # 'rival', 'CODequipo', 'CODrival', 'info']

        mercadosAMirar = [None] * (maxJornada + 1)

        for key in keysJugDatos:
            resultado[key] = defaultdict(listaDatos)
        for key in (keysJugInfo + ['activo']):
            resultado['I-' + key] = dict()

        for jornada in self.mercadoJornada:
            mercadosAMirar[jornada] = self.mercadoJornada[jornada]
        ultMercado = self.mercado[self.ultimoMercado]

        if ultMercado != self.mercado[mercadosAMirar[-1]]:
            maxJornada += 1
            mercadosAMirar.append(self.ultimoMercado)

        for i in range(len(mercadosAMirar)):
            mercadoID = mercadosAMirar[i]
            if not mercadoID:
                continue

            mercado = self.mercado[mercadoID]

            for jugSM in mercado.PlayerData:
                jugadorData = mercado.PlayerData[jugSM]

                IDjugador = cacheLinks.get(jugadorData['kiaLink'], dataPlants[jugadorData['IDequipo']].getCode(
                    nombre=RetocaNombreJugador(jugadorData['nombre']), esJugador=True, umbral=1))

                if isinstance(IDjugador, str):
                    cacheLinks[jugadorData['kiaLink']] = IDjugador
                    cacheEqNom[jugadorData['IDequipo']][jugadorData['nombre']] = IDjugador
                    codJugador = IDjugador
                else:
                    pendienteLinks[jugadorData['kiaLink']].append((i, jugadorData))

                    print("Incapaz de encontrar ID para '%s' (%s,%s): %s" % (
                        jugadorData['kiaLink'], jugadorData['nombre'], jugadorData['equipo'], IDjugador))
                    continue


                actualizaResultado(resultado, codJugador, i, jugadorData)
                codigosUsados.add(codJugador)

            for jugadorData in mercado.noKiaLink:
                IDjugador = cacheEqNom[jugadorData['IDequipo']].get(jugadorData['nombre'],
                                                                    dataPlants[jugadorData['IDequipo']].getCode(
                                                                        nombre=RetocaNombreJugador(
                                                                            jugadorData['nombre']), esJugador=True,
                                                                        umbral=1))
                if isinstance(IDjugador, str):
                    cacheEqNom[jugadorData['IDequipo']][jugadorData['nombre']] = IDjugador
                    codJugador = IDjugador
                else:
                    pendienteEqNom[jugadorData['IDequipo']][jugadorData['nombre']].append((i, jugadorData))
                    print("Incapaz de encontrar ID para %s (%s): %s" % (
                        jugadorData['nombre'], jugadorData['equipo'], IDjugador))
                    continue

                actualizaResultado(resultado, codJugador, i, jugadorData)
                codigosUsados.add(codJugador)

        contNocode = 1
        for kiaLink, listaMercs in pendienteLinks.items():
            nombresL = {i['nombre'] for j, i in listaMercs}
            codeSet = set()

            for codJug, nameSet in nombresJugadores.items():
                if codJug in codigosUsados:
                    continue

                for auxNombre in nombresL:
                    auxRet = NormalizaCadena(RetocaNombreJugador(auxNombre))

                    for nomTest in nameSet:
                        auxTest = NormalizaCadena(RetocaNombreJugador(nomTest))

                        if comparaNombresPersonas(auxRet, auxTest):
                            codeSet.add(codJug)
                            break

            IDjugador = onlySetElement(codeSet)
            if isinstance(IDjugador, str):
                codJugador = IDjugador
            else:
                codJugador = "NOCODE%03i" % contNocode
                contNocode += 1

            for i, jugadorData in listaMercs:
                actualizaResultado(resultado, codJugador, i, jugadorData)

        for jugSM in resultado['lesion']:
            resultado['I-activo'][jugSM] = (jugSM in ultMercado.PlayerData)

        return resultado

    def superManager2dataframe(self, nombresJugadores=None, infoPlants=None):
        """ Extrae un dataframe con los últimos datos de todos los jugadores que han jugado en la temporada.
        """
        DFcolNewNames = {'I-codJugador': 'codigo', 'I-cupo': 'cupo', 'I-pos': 'pos', 'I-CODrival': 'CODrival'}

        keys2remove = ['I-codJugador']
        datos = self.extraeDatosJugadoresMercado(nombresJugadores=nombresJugadores, infoPlants=infoPlants)

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
        dfResult['lesion'] = dfResult['lesion'].map(bool2esp)
        dfResult['Alta'] = dfResult['activo'].map(bool2esp)

        # dfResult['infoLesion'] = dfResult.apply(datosLesionMerc, axis=1)
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
            mercAnt = (self.mercado[listaMercs[jornadaIDX - 1]]).PlayerData if jornadaIDX > 0 else {}

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

    def actualizaTraducciones(self, datosACB=None):
        if datosACB is None:
            return

        if not hasattr(self, "traducciones"):
            self.traducciones = {'equipos': {'n2c': defaultdict(set), 'c2n': defaultdict(set), 'n2i': defaultdict(set),
                                             'i2n': defaultdict(set), 'i2c': defaultdict(set), 'c2i': defaultdict(set)},
                                 'jugadores': {'j2c': defaultdict(set), 'c2j': defaultdict(set)}}

        # for codigo, nombres in datosACB.tradJugadores['id2nombres'].items():
        #     self.addTraduccionJugador(codigo, nombres)

        for codigo, nombres in datosACB.Calendario.tradEquipos['c2n'].items():
            if (codigo not in self.traducciones['equipos']['c2n']):
                self.changed = True
            for nombre in nombres:
                if (nombre not in self.traducciones['equipos']['c2n'][codigo]):
                    self.changed = True
                self.traducciones['equipos']['n2c'][nombre].add(codigo)
                self.traducciones['equipos']['c2n'][codigo].add(nombre)

        for id, codigos in datosACB.Calendario.tradEquipos['i2c'].items():
            if (id not in self.traducciones['equipos']['i2c']):
                self.changed = True
            for codigo in codigos:
                if (codigo not in self.traducciones['equipos']['i2c'][id]):
                    self.changed = True
                self.traducciones['equipos']['i2c'][id].add(codigo)
                self.traducciones['equipos']['c2i'][codigo].add(id)

        for id, nombres in datosACB.Calendario.tradEquipos['i2n'].items():
            if (id not in self.traducciones['equipos']['i2n']):
                self.changed = True
            for nombre in nombres:
                if (nombre not in self.traducciones['equipos']['i2n'][id]):
                    self.changed = True
                self.traducciones['equipos']['i2n'][id].add(nombre)
                self.traducciones['equipos']['n2i'][nombre].add(id)

    # def addTraduccionJugador(self, codigo, nombres):
    #     listNombres = listize(nombres)
    #
    #     for nombre in listNombres:
    #         if (nombre not in self.traducciones['jugadores']['j2c']) or (
    #                 codigo not in self.traducciones['jugadores']['j2c'][nombre]) or (
    #                 codigo not in self.traducciones['jugadores']['c2j']) or (
    #                 nombre not in self.traducciones['jugadores']['c2j'][codigo]):
    #             self.changed = True
    #         self.traducciones['jugadores']['j2c'][nombre].add(codigo)
    #         self.traducciones['jugadores']['c2j'][codigo].add(nombre)

    def getMercado(self, browser):
        browser.follow_link("mercado")

        mercadoData = MercadoPageContent({'source': browser.get_url(), 'data': browser.get_current_page()}, self)
        return mercadoData

    def getJornadasJugadas(self):
        result = set()
        for l in self.ligas:
            result = result.union(set(self.ligas[l].getListaJornadas()))

        return result


class ResultadosJornadas(object):

    def __init__(self, jornada, supermanager, excludelist=set()):
        self.resultados = defaultdict(dict)
        self.socio2equipo = dict()
        self.equipo2socio = dict()

        self.types = {'asistencias': int, 'broker': int, 'key': str, 'puntos': int, 'rebotes': int, 'triples': int,
                      'valJornada': decimal.Decimal}

        for team in supermanager.jornadas[jornada].data:
            datosJor = supermanager.jornadas[jornada].data[team]
            socio = manipulaSocio(datosJor['socio'])

            if socio in excludelist:
                continue
            self.socio2equipo[socio] = team
            self.equipo2socio[team] = socio

            self.resultados[socio]['valJornada'] = (self.types['valJornada'])(
                datosJor['value'])

            if jornada in supermanager.__getattribute__('general'):
                self.resultados[socio]['general'] = (self.types['valJornada'])(
                    supermanager.general[jornada].data[team]['value'])

            for comp in ['puntos', 'rebotes', 'triples', 'asistencias', 'broker']:
                if jornada in supermanager.__getattribute__(comp):
                    if jornada == 1 or jornada - 1 in supermanager.__getattribute__(comp):
                        if comp == 'broker':
                            self.resultados[socio]['saldo'] = (self.types[comp])(
                                supermanager.__getattribute__(comp)[jornada].data[team]['value'])

                        self.resultados[socio][comp] = (self.types[comp])(
                            supermanager.__getattribute__(comp)[jornada].data[team]['value'])
                        if jornada != 1:
                            self.resultados[socio][comp] -= \
                                (self.types[comp])(supermanager.__getattribute__(comp)[jornada - 1].data[team]['value'])

            self.updateVal2Team()

    def updateVal2Team(self):
        aux = defaultdict(lambda: defaultdict(set))
        for e in self.resultados:
            for k in self.resultados[e]:
                aux[k][self.resultados[e][k]].add(e)

        self.valor2team = dict()
        for k in aux:
            self.valor2team[k] = dict(aux[k])

    def puntos2team(self, comp, valor):
        if valor not in self.valor2team[comp]:
            return []
        return self.valor2team[comp][valor]

    def valoresSM(self):
        result = defaultdict(set)

        for equipo in self.resultados:
            for comp in self.resultados[equipo]:
                result[comp].add(self.resultados[equipo][comp])

        return result

    def comparaAgregado(self, team, agregado):
        for comp in ['broker', 'valJornada', 'puntos', 'rebotes', 'triples', 'asistencias']:
            if agregado[comp] != self.resultados[team][comp]:
                return False
        return True

    def listaSocios(self):
        return list(self.socio2equipo.keys())

    def listaEquipos(self):
        return list(self.equipo2socio.keys())

    def reduceLista(self, equipo):
        if isinstance(equipo, str):
            teams2add = [equipo]
        elif isinstance(equipo, Iterable):
            teams2add = equipo
        else:
            raise (TypeError, "reduceLista: tipo incorrecto para 'equipos'")

        equiposFallan = [e for e in teams2add if e not in self.resultados]

        if equiposFallan:
            raise (ValueError, "%s no están en la liga." % ", ".join(equiposFallan))

        result = deepcopy(self)
        for e in self.listaEquipos():
            if e not in teams2add:
                result.resultados.pop(e)
        result.updateVal2Team()

        return result

    def resSocio2Str(self, socio):
        keylist = ('valJornada', 'broker', 'puntos', 'rebotes', 'triples', 'asistencias', 'saldo', 'general')
        key2label = {'valJornada': 'Val: %7.2f', 'broker': 'Broker: %8i', 'puntos': 'Puntos: %4d',
                     'rebotes': 'Rebotes: %4d', 'triples': 'Triples: %4d', 'asistencias': 'Asistencias: %4d',
                     'saldo': 'Saldo: %10d', 'general': 'General: %7.2f'}
        FORMAT = " ".join([key2label[k] for k in keylist if k in self.resultados[socio]])
        DATA = tuple([self.resultados[socio][k] for k in keylist if k in self.resultados[socio]])

        return FORMAT % DATA


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

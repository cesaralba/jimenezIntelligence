# -*- coding: utf-8 -*-

import re
from collections import defaultdict
from time import gmtime, strftime, strptime

import pandas as pd
from babel.numbers import decimal, parse_decimal
from bs4 import BeautifulSoup

from Utils.Misc import FORMATOtimestamp, onlySetElement
from .ManageSMDataframes import datosPosMerc, datosProxPartidoMerc
from .PlantillaACB import descargaPlantillasCabecera
from .SMconstants import CUPOCORTO, CUPOS, POSICIONCORTA, POSICIONES, bool2esp

INCLUDEPLAYERDATA = False


class MercadoPageCompare():

    def __init__(self, old, new):

        if not isinstance(old, MercadoPageContent) and isinstance(new, MercadoPageContent):
            errorStr = ""
            if not isinstance(old, MercadoPageContent):
                errorStr += "Type for original data '%s' is not supported. " % type(old)
            if not isinstance(new, MercadoPageContent):
                errorStr += "Type for new data '%s' is not supported. " % type(new)

            raise TypeError(errorStr)

        # Am I a metadata freak?
        self.timestamps = {}
        self.timestamps['old'] = old.timestamp
        self.timestamps['new'] = new.timestamp

        self.sources = {}
        self.sources['old'] = old.source
        self.sources['new'] = new.source

        self.changes = False

        self.teamRenamed = False
        self.newTeams = []
        self.delTeams = []
        self.teamTranslationsOld2New = {}
        self.teamTranslationsNew2Old = {}

        self.playerChanges = defaultdict(lambda: defaultdict(str))

        self.bajas = []
        self.altas = []
        self.lesionado = []
        self.curado = []

        self.cambRival = 0
        self.contCambEquipo = 0
        cambEquipo = {}
        self.newRivals = defaultdict(int)
        origTeam = defaultdict(int)
        destTeam = defaultdict(int)
        self.cambioJornada = False

        oldPlayersID = set(old.PlayerData.keys())
        newPlayersID = set(new.PlayerData.keys())
        oldTeams = set(old.Team2Player.keys())
        newTeams = set(new.Team2Player.keys())
        self.teamsJornada = len(newTeams)

        if oldTeams != newTeams:
            self.teamRenamed = True
            newShowingTeams = newTeams - oldTeams
            nonShowingTeams = oldTeams - newTeams
            if len(newShowingTeams) == 1:
                self.teamTranslationsNew2Old[list(newShowingTeams)[0]] = list(nonShowingTeams)[0]
                self.teamTranslationsOld2New[list(nonShowingTeams)[0]] = list(newShowingTeams)[0]
            else:
                self.newTeams = list(newShowingTeams)
                self.delTeams = list(nonShowingTeams)

        bajasID = oldPlayersID - newPlayersID
        altasID = newPlayersID - oldPlayersID
        siguenID = oldPlayersID & newPlayersID

        if bajasID:
            self.changes = True
            self.bajas = [old.PlayerData[x] for x in bajasID]
            for key in bajasID:
                self.playerChanges[key]['key'] = self.playerInfo(old, key)
                self.playerChanges[key]['baja'] += "Es baja en '{}'. ".format(old.PlayerData[key]['equipo'])

        if altasID:
            self.changes = True
            self.altas = [new.PlayerData[x] for x in altasID]
            for key in altasID:
                self.playerChanges[key]['key'] = self.playerInfo(new, key)
                self.playerChanges[key]['alta'] += "Es alta en '{}'. ".format(new.PlayerData[key]['equipo'])

        for key in siguenID:
            oldPlInfo = old.PlayerData[key]
            newPlInfo = new.PlayerData[key]

            if oldPlInfo['equipo'] != newPlInfo['equipo']:
                oldTeam = oldPlInfo['equipo']
                newTeam = newPlInfo['equipo']

                self.contCambEquipo += 1
                origTeam[oldTeam] += 1
                destTeam[newTeam] += 1
                self.playerChanges[key]['key'] = self.playerInfo(new, key)
                self.playerChanges[key]['cambio'] += "Pasa de '{}' a '{}'. ".format(oldTeam, newTeam)

                cambEquipo[key] = "{} pasa de {} a {}".format(key, oldPlInfo['equipo'], newPlInfo['equipo'])

            if oldPlInfo['rival'] != newPlInfo['rival']:
                self.changes = True
                # oldRival = oldPlInfo['rival']
                newRival = newPlInfo['rival']

                self.newRivals[newRival] += 1
                self.cambRival += 1

            if oldPlInfo['lesion'] != newPlInfo['lesion']:
                self.changes = True
                if newPlInfo['lesion']:
                    self.playerChanges[key]['key'] = "{} ({},{})".format(new.PlayerData[key]['nombre'], key,
                                                                         new.PlayerData[key]['equipo'])
                    self.playerChanges[key]['lesion'] += "Se ha lesionado. "
                    self.changes = True
                    self.lesionado.append(key)
                else:
                    self.playerChanges[key]['key'] = "{} ({},{})".format(new.PlayerData[key]['nombre'], key,
                                                                         new.PlayerData[key]['equipo'])
                    self.playerChanges[key]['salud'] += "Se ha recuperado. "
                    self.changes = True
                    self.curado.append(key)

            if 'info' in oldPlInfo or 'info' in newPlInfo:
                if 'info' in oldPlInfo:
                    if 'info' in newPlInfo:
                        if oldPlInfo['info'] != newPlInfo['info']:
                            self.changes = True
                            self.playerChanges[key]['key'] = self.playerInfo(new, key)
                            self.playerChanges[key]['info'] += "Info pasa de '{}' a '{}'. ".format(oldPlInfo['info'],
                                                                                                   newPlInfo['info'])
                    else:
                        self.changes = True
                        self.playerChanges[key]['key'] = self.playerInfo(new, key)
                        self.playerChanges[key]['info'] += "Info eliminada '{}'. ".format(oldPlInfo['info'])
                else:
                    self.changes = True
                    self.playerChanges[key]['key'] = self.playerInfo(new, key)
                    self.playerChanges[key]['info'] += "Info nueva '{}'. ".format(newPlInfo['info'])

        if (len(self.newRivals) == self.teamsJornada) or (len(self.newRivals) > 4):
            self.cambioJornada = True

    def __repr__(self):
        changesMSG = "hubo cambios." if self.changes else "sin cambios."
        result = "Comparación entre {} ({}) y {} ({}): {}\n\n".format(self.sources['old'],
                                                                      strftime(FORMATOtimestamp,
                                                                               self.timestamps['old']),
                                                                      self.sources['new'],
                                                                      strftime(FORMATOtimestamp,
                                                                               self.timestamps['new']),
                                                                      changesMSG)

        if self.cambioJornada:
            result += "Cambio de jornada!\n\n"

        if self.newRivals:
            result += "NewRivals: {} \n\n".format(self.newRivals)

        if self.teamRenamed:
            result += "Equipos renombrados: {}\n".format(len(self.teamTranslationsNew2Old))
            for team in self.teamTranslationsOld2New.keys():
                result += "  '{}' pasa a ser '{}'\n".format(team, self.teamTranslationsOld2New[team])
        if self.newTeams:
            listaTeams = self.newTeams
            listaTeams.sort()
            result += "Nuevos equipos ({}): {}\n".format(len(self.newTeams), listaTeams)
        if self.delTeams:
            listaTeams = self.delTeams
            listaTeams.sort()
            result += "Equipos no juegan ({}): {}\n".format(len(self.delTeams), listaTeams)

        if self.teamRenamed or self.newTeams or self.delTeams:
            result += "\n"

        if self.contCambEquipo:
            result += "Cambios de equipo: {}\n".format(self.contCambEquipo)

        if self.altas:
            result += "Altas: {}\n".format(len(self.altas))
            # print("Altas:",self.altas)

        if self.bajas:
            result += "Bajas: {}\n".format(len(self.bajas))
            # print("Bajas:",self.bajas)

        if self.lesionado:
            result += "Lesionados: {}\n".format(len(self.lesionado))
            # print("Lesionados:",self.lesionado)

        if self.curado:
            result += "Recuperados: {}\n".format(len(self.curado))
            # print("Curados:",self.curado)

        if self.altas or self.bajas or self.lesionado or self.curado:
            result += "\n"

        orderList = list(self.playerChanges.keys())
        orderList.sort(key=lambda x: (self.playerChanges[x]['key']).lower())
        for key in orderList:
            playerChangesInfo = self.playerChanges[key]
            result += playerChangesInfo['key'] + ": "
            for item in [x for x in playerChangesInfo.keys() if x != 'key']:
                result += playerChangesInfo[item]
            result += "\n"

        if self.playerChanges:
            result += "\n"

        result += "\n"

        return result

    def playerInfo(self, mercado, key):
        datos = mercado.PlayerData[key]
        info = [key, POSICIONCORTA[datos['pos']], CUPOCORTO[datos['cupo']], datos['equipo']]
        if datos['lesion']:
            info.append('Lesionado')

        return "{} ({})".format(datos['nombre'], ",".join(info))


class MercadoPageContent():

    def __init__(self, textPage, datosSM=None):
        self.timestamp = gmtime()
        self.source = textPage['source']
        self.PositionsCounter = defaultdict(int)
        self.PlayerData = {}
        self.PlayerByPos = defaultdict(list)
        self.Team2Player = defaultdict(set)
        self.noKiaLink = []

        if (type(textPage['data']) is str):
            soup = BeautifulSoup(textPage['data'], "html.parser")
        elif (type(textPage['data']) is BeautifulSoup):
            soup = textPage['data']
        else:
            raise NotImplementedError("MercadoPageContent: type of content '%s' not supported" % type(textPage['data']))

        positions = soup.find_all("table", {"class": "listajugadores"})

        for pos in positions:
            position = pos['id']

            for player in pos.find_all("tr"):
                player_data = player.find_all("td")
                if not player_data:
                    continue

                fieldTrads = {'foto': ['foto'], 'jugador': ['jugador'], 'equipo': ['equipo'],
                              'promedio': ['promVal', 'valJornada', 'seMantiene'],
                              'precio': ['precio', 'enEquipos%'], 'val': ['prom3Jornadas'],
                              'balance': ['sube15%'], 'baja': ['baja15%'], 'rival': ['rival'], 'iconos': ['iconos']}

                result = {'proxFuera': False, 'lesion': False, 'cupo': 'normal'}
                result['pos'] = position
                self.PositionsCounter[position] += 1
                for data in player_data:
                    classes = data.attrs['class']
                    # print("AQUI",data)

                    if 'iconos' in classes:
                        for icon in data.find_all("img"):
                            if icon['title'] == "Extracomunitario":
                                result['cupo'] = 'Extracomunitario'
                            elif icon['title'] == "Español":
                                result['cupo'] = "Español"
                            elif icon['title'] == "Lesionado":
                                result['lesion'] = True
                            elif icon['alt'] == "Icono de más información":
                                result['info'] = icon['title']
                            else:
                                print("No debería llegar aquí: ", icon)
                        continue
                    elif "foto" in classes:
                        img_link = data.img['src']
                        result['foto'] = img_link
                        result['nombre'] = data.img['title']

                        # if result['nombre'] in datosSM.traducciones['jugadores']['j2c']:
                        #     tradsPosibles = datosSM.traducciones['jugadores']['j2c']
                        # elif traductor:
                        #     nombreRetoc = RetocaNombreJugador(result['nombre'])
                        #     tradsPosibles = traductor.BuscaTraduccion(nombreRetoc, 0)
                        #
                        # if isinstance(tradsPosibles, str):  # Solo un codigo!
                        #     result['codJugador'] = tradsPosibles
                        # else:  # Set or None
                        #     print("Troublesome player", result['nombre'], result)
                        #     result['posibles'] = tradsPosibles
                        continue

                    elif 'jugador' in classes:
                        if data.a:
                            result['kiaLink'] = data.a['href']
                            # if traductor is None:
                            #     result['codJugador'] = result['kiaLink']
                        continue
                    elif 'equipo' in classes:
                        result['equipo'] = data.img['title']
                        if result['equipo'] in datosSM.traducciones['equipos']['n2c']:
                            result['CODequipo'] = sorted(datosSM.traducciones['equipos']['n2c'][result['equipo']])[0]
                        auxId = datosSM.traducciones['equipos']['c2i'].get(result['CODequipo'], None)
                        result['IDequipo'] = onlySetElement(auxId)
                        continue
                    elif 'rival' in classes:
                        for icon in data.find_all('img'):
                            if icon['title'].lower() == "partido fuera":
                                result['proxFuera'] = True
                            else:
                                result['rival'] = icon['title']
                                if result['rival'] in datosSM.traducciones['equipos']['n2c']:
                                    result['CODrival'] = \
                                        sorted(datosSM.traducciones['equipos']['n2c'][result['rival']])[0]
                                auxId = datosSM.traducciones['equipos']['c2i'][result['CODrival']]
                                result['IDrival'] = onlySetElement(auxId)
                        continue
                    else:
                        auxval = data.get_text().strip()
                        classOrig = classes[0]

                        for auxClass in fieldTrads[classOrig]:
                            if auxClass not in result:
                                classCel = auxClass
                                break
                        if '%' in auxval and classCel == 'enEquipos%':
                            auxval = auxval.replace("%", "")
                        result[classCel] = parse_decimal(auxval, locale="de")

                try:
                    codJugador = result['kiaLink']
                except KeyError:
                    print("Problemas con jugador '%s' (%s): no tiene kiaLink (?)" % (
                        result.get('nombre', "Nombre desc"), result.get('equipo', "Equipo desc")))
                    self.noKiaLink.append(result)
                    continue

                self.PlayerData[codJugador] = result
                self.PlayerByPos[position].append(codJugador)
                self.Team2Player[result['equipo']].add(codJugador)

                # if result.get('codJugador', None):
                #     self.PlayerData[result['codJugador']] = result
                #     self.PlayerByPos[position].append(result['codJugador'])
                #     self.Team2Player[result['equipo']].add(result['codJugador'])
                # else:
                #     if 'posibles' in result:
                #         jugadoresPendientes.append(result)

        # if jugadoresPendientes:
        #     self.pendientes = jugadoresPendientes
        #     self.buscaCodigoJugadoresPendientes(infoPlantillas=None)
        #     # TODO: ¿Qué hacer con los pendientes?
        #
        # print(jugadoresPendientes)

        # if datosSM is not None:
        #     for cod, jugData in self.PlayerData.items():
        #         datosSM.addTraduccionJugador(cod, RetocaNombreJugador(jugData['nombre']))

    def setTimestampFromStr(self, timeData):
        ERDATE = re.compile(r".*-(\d{4}\d{2}\d{2}(\d{4})?)\..*")
        ermatch = ERDATE.match(timeData)
        if ermatch:
            if ermatch.group(2):
                self.timestamp = strptime(ermatch.group(1), "%Y%m%d%H%M")
            else:
                self.timestamp = strptime(ermatch.group(1), "%Y%m%d")

    def diff(self, otherData):
        return MercadoPageCompare(self, otherData)

    def __ne__(self, other):
        diff = self.diff(other)
        return diff.changes

    def getPlayersByPosAndCupo(self, jornada=0, temporadaExtr=None):
        """
        Extrae un diccionario con informaciones de los jugadores que han participado en determinada jornada
        :param jornada:
        :param temporadaExtr:
        :return:
        """
        result = {'data': defaultdict(list),
                  'cont': [0] * len(POSICIONES) * len(CUPOS)}
        indexResult = {}

        aux = 0
        for pos in POSICIONES:
            indexResult[pos] = {}
            for cupo in CUPOS:
                indexResult[pos][cupo] = aux
                aux += 1
        result['indexes'] = indexResult

        for cod in self.PlayerData:
            datos = self.PlayerData[cod]
            i = indexResult[datos['pos']][datos['cupo']]
            datoAux = [cod, int(datos['valJornada'] * 100)]
            if temporadaExtr:  # ['puntos', 'rebotes', 'triples', 'asistencias']
                for cat in ['P', 'REB-T', 'T3-C', 'A']:
                    if temporadaExtr[cat][cod][jornada - 1]:
                        datoAux.append(temporadaExtr[cat][cod][jornada - 1])
                    else:
                        datoAux.append(0)

            (result['data'][i]).append(datoAux)
            result['cont'][i] += 1

        return result

    def cuentaCupos(self, lista):
        result = defaultdict(int)

        for p in lista:
            result[self.PlayerData[p]['cupo']] += 1

        return result

    def timestampKey(self):
        return strftime("%Y%m%d-%H%M%S", self.timestamp)

    def asignaCodigosEquipos(self, datosACB=None):
        if not datosACB:
            return

        if not hasattr(self, "equipo2codigo"):
            self.equipo2codigo = dict()

        for jugador in self.PlayerData:
            equipo = self.PlayerData[jugador]['equipo']
            rival = self.PlayerData[jugador]['rival']
            if equipo in self.equipo2codigo:
                self.PlayerData[jugador]['CODequipo'] = self.equipo2codigo[equipo]
            else:
                CODequipo = datosACB.Calendario.buscaEquipo2CodigoDistancia(equipo)
                if CODequipo:
                    self.PlayerData[jugador]['CODequipo'] = CODequipo
                    self.equipo2codigo[equipo] = CODequipo
                else:
                    print("asignaCodigos: incapaz de encontrar código para '%s'." % equipo)

            if rival in self.equipo2codigo:
                self.PlayerData[jugador]['CODrival'] = self.equipo2codigo[rival]
            else:
                CODrival = datosACB.Calendario.buscaEquipo2CodigoDistancia(rival)
                if CODrival:
                    self.PlayerData[jugador]['CODrival'] = CODrival
                    self.equipo2codigo[rival] = CODrival
                else:
                    print("asignaCodigos: incapaz de encontrar código para '%s'." % rival)

    def mercado2dataFrame(self):
        renombraCampos = {'codJugador': 'codigo'}
        # 'codigo': 'category',
        colTypes = {'CODequipo': 'category', 'CODrival': 'category', 'cupo': 'category',
                    'equipo': 'category', 'lesion': 'category', 'pos': 'category', 'precio': 'int64',
                    'prom3Jornadas': 'float64', 'promVal': 'float64', 'proxFuera': 'bool', 'rival': 'category',
                    'esLocal': 'bool'}

        def jugador2dataframe(jugador):
            dictJugador = dict()
            for dato in jugador:
                if dato in ['enEquipos%', 'sube15%', 'seMantiene', 'baja15%', 'foto', 'kiaLink', ]:
                    continue
                dictJugador[dato] = jugador[dato]

            dfresult = pd.DataFrame.from_dict(dictJugador, orient='index').transpose().rename(renombraCampos,
                                                                                              axis='columns')
            return (dfresult)

        dfJugs = [jugador2dataframe(jugador) for jugador in self.PlayerData.values()] + [jugador2dataframe(jugador) for
                                                                                         jugador in self.noKiaLink]
        dfResult = pd.concat(dfJugs, axis=0, ignore_index=True, sort=True)
        dfResult['esLocal'] = ~(dfResult['proxFuera'].astype('bool'))
        dfResult['ProxPartido'] = dfResult.apply(datosProxPartidoMerc, axis=1)
        dfResult['pos'] = dfResult.apply(datosPosMerc, axis=1)
        dfResult.loc[dfResult['info'].isna(), 'info'] = ""
        dfResult['lesion'] = dfResult['lesion'].map(bool2esp)
        # dfResult['infoLesion'] = dfResult.apply(datosLesionMerc, axis=1)

        return (dfResult.astype(colTypes))

    def buscaCodigoJugadoresPendientes(self, infoPlantillas=None):

        dataPlantillas = descargaPlantillasCabecera() if infoPlantillas is None else infoPlantillas

        newPendientes = []

        for jug in self.pendientes:
            posTrads = jug.get('posibles', set()) if 'posibles' in jug and jug['posibles'] is not None else set()
            print(jug['nombre'], posTrads, jug['IDequipo'])
            resCode = onlySetElement(dataPlantillas[jug['IDequipo']].getCode(jug['nombre'], dorsal=None, esJugador=True,
                                                                             esTecnico=False))

            if isinstance(resCode, (str, bytes)):
                jug['codJugador'] = resCode
                if 'posibles' in jug:
                    jug.pop('posibles')
                self.PlayerData[jug['codJugador']] = jug
                self.PlayerByPos[jug['pos']].append(jug['codJugador'])
                self.Team2Player[jug['equipo']].add(jug['codJugador'])
            else:
                jug['posibles'] = resCode
                newPendientes.append(jug)

        self.pendientes = newPendientes

    def __repr__(self):
        result = "Mercado SM. Fuente '%s'. Timestamp: %s" % (self.source, strftime("%Y-%m-%d %H:%M", self.timestamp))
        return result

    __str__ = __repr__


class NoSuchPlayerException(Exception):

    def __init__(self, codigo, source, timestamp):
        Exception.__init__(self, )


class BadSetException(Exception):

    def __init__(self, msg):
        Exception.__init__(self, msg)


class GroupPlayer(object):

    # TODO: Incluir merge con estadisticas y coste (precio de la jornada anterior)
    def __init__(self, lista=[], mercado=None):

        self.source = None
        self.timestamp = None
        self.players = set()
        self.valoracion = decimal.Decimal(0.0)
        self.precio = decimal.Decimal(0.0)
        self.cupos = defaultdict(int)
        self.posiciones = defaultdict(int)
        self.estads = {}
        self.playerData = {}

        if mercado is None and len(lista):
            raise BadSetException("List of player provided but no mercado")

        if mercado:
            self.source = mercado.source
            self.timestamp = mercado.timestamp
        else:
            return

        for p in lista:
            if p in self.players:
                continue
            if p in mercado.PlayerData:
                self.IncludePlayer(mercado.PlayerData[p])
            else:
                raise NoSuchPlayerException("Unable find player [{}] in mercado from {}@{}".format(
                    p, mercado.source, mercado.timestamp))

    def IncludePlayer(self, playerInfo):
        cod = playerInfo['codJugador']

        if cod in self.players:
            return
        self.cupos[playerInfo['cupo']] += 1
        self.posiciones[playerInfo['pos']] += 1
        self.valoracion += playerInfo['valJornada']
        self.precio += playerInfo['precio']
        self.players.add(cod)
        self.playerData[cod] = playerInfo

    def Merge(self, *args):

        totalLength = 0
        for other in args:
            if other is not GroupPlayer:
                raise BaseException("Can't add a {} to a GroupPlayer".format(type(other)))
            if (self.mercado != other.mercado) or (self.timestamp != other.timestamp):
                raise BaseException("Can't merge players from different mercado data {}@{} and {}@{}".format(
                    self.source, self.timestamp, other.source, other.timestamp))
            totalLength += len(other.players)

        result = GroupPlayer()

        for gr in [self] + args:
            for p in gr.players:
                result.IncludePlayer(gr.playerData[p])

        return result

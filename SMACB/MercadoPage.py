from bs4 import BeautifulSoup
from time import gmtime

from collections import defaultdict

import re

from babel.numbers import parse_decimal

class MercadoPageContent():

    def __init__(self, textPage):
        self.timestamp = gmtime()
        self.source = textPage['source']
        self.contadorNoFoto = 0
        self.NoFoto2Nombre = {}
        self.Nombre2NoFoto = {}
        self.PositionsCounter = defaultdict(int)
        self.PlayerData = {}
        self.PlayerByPos = defaultdict(list)
        self.Team2Player = defaultdict(set)

        if (type(textPage['data']) is str):
            soup = BeautifulSoup(textPage['data'], "html.parser")
        elif (type(textPage['data']) is BeautifulSoup):
            soup = textPage['data']
        else:
            raise NotImplementedError("MercadoPageContent: type of content '%s' not supported" % type(textPage['data']))

        positions = soup.find_all("table", {"class":"listajugadores"})

        for pos in positions:
            position = pos['id']

            for player in pos.find_all("tr"):
                player_data = player.find_all("td")
                player_data or next

                fieldTrads = { 'foto' : ['foto'],
                               'jugador' : ['jugador'],
                               'equipo' : ['equipo'],
                               'promedio' : ['promVal', 'valJornada', 'seMantiene'],
                               'precio' : ['precio', 'enEquipos%'],
                               'val' : ['prom3Jornadas'],
                               'balance' : ['sube15%'],
                               'baja' : ['baja15%'],
                               'rival' : ['rival'],
                               'iconos' : ['iconos']
                               }

                result = { 'proxFuera': False , 'lesion': False,
                          'cupo': 'normal'  }
                result['pos'] = position
                self.PositionsCounter[position] += 1
                for data in player_data:
                    # print(data,data['class'])

                    dataid = (fieldTrads.get(data['class'][0])).pop(0)
                    if dataid == "foto":
                        img_link = data.img['src']
                        result['foto'] = img_link
                        result['nombre'] = data.img['title']
                        auxre = re.search(r'J(.{3})LACB([0-9]{2})\.jpg', img_link)
                        if auxre:
                            result['codJugador'] = auxre.group(1)
                            result['temp'] = auxre.group(2)
                        else:
                            jugCode = "NOFOTO%03i" % self.contadorNoFoto
                            self.contadorNoFoto += 1
                            self.NoFoto2Nombre[jugCode] = result['nombre']
                            self.Nombre2NoFoto[result['nombre']] = jugCode
                            result['codJugador'] = jugCode
                    elif dataid == 'jugador':
                        result['kiaLink'] = data.a['href']
                    elif dataid == 'iconos':
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

                    elif dataid == 'equipo':
                        result['equipo'] = data.img['title']
                    elif dataid == 'rival':
                        for icon in data.find_all('img'):
                            if icon['title'] == "Partido fuera":
                                result['proxFuera'] = True
                            else:
                                result['rival'] = icon['title']
                    else:
                        auxval = data.get_text().strip()
                        if dataid == "enEquipos%":
                            auxval = auxval.replace("%", "")
                        result[dataid] = parse_decimal(auxval, locale="de")

                        # print("Not treated %s" % dataid, data,)
                if result.get('codJugador'):
                    self.PlayerData[result['codJugador']] = result
                    self.PlayerByPos[position].append(result['codJugador'])
                    self.Team2Player[result['equipo']].add(result['codJugador'])

    def __repr__(self):
        return str({'timestamp':self.timestamp,
                    'source':self.source,
                    'NoFoto2Nombre':self.NoFoto2Nombre,
                    'Nombre2NoFoto':self.Nombre2NoFoto,
                    'PositionsCounter':self.PositionsCounter,
                    'PlayerData':self.PlayerData,
                    'PlayerByPos':self.PlayerByPos,
                    'Team2Player':self.Team2Player
                    })

    def Compare(self, otherData):

        changes = 0
        cambRival = 0
        cambEquipo = {}
        sanan = []
        lesion = []
        newInfo = {}
        changedInfo = {}
        clearedInfo = {}

        if not type(otherData) is MercadoPageContent:
            raise TypeError("MercadoPageContent.Compare: Type for comparison " +
                            "'%s' is not supported" % type(otherData))

        selfPlayersID = set(self.PlayerData.keys())
        otherPlayersID = set(otherData.PlayerData.keys())

        bajasID = selfPlayersID - otherPlayersID
        altasID = otherPlayersID - selfPlayersID
        siguenID = selfPlayersID & otherPlayersID

        if bajasID:
            changes += 1
        if altasID:
            changes += 1

        for key in siguenID:
            curr = self.PlayerData[key]
            other = otherData.PlayerData[key]

            if curr['rival'] != other['rival']:
                cambRival += 1

            if curr['equipo'] != other['equipo']:
                changes += 1
                cambEquipo[key] = "{} pasa de {} a {}".format(key,
                                                             curr['equipo'],
                                                             other['equipo'])

            if curr['lesion'] != other['lesion']:
                changes += 1
                if other['lesion']:
                    lesion.append(key)
                else:
                    sanan.append(key)

            if 'info' in curr or 'info' in other:
                if 'info' in curr:
                    if 'info' in other:
                        if curr['info'] != other['info']:
                            changedInfo[key] = "Info changed from '{}' to '{}'.".format(curr['info'], other['info'])
                            changes += 1
                    else:
                        changes += 1
                        clearedInfo[key] = "Info cleared: '{}.".format(curr['info'])
                else:
                    changes += 1
                    newInfo[key] = "Info new: '{}.".format(other['info'])
        if changes:
            pass

        if cambEquipo:
            print("MercadoPageContent.Compare: {}: cambios de equipo ".format(otherData.source),
                  cambEquipo)

        if cambRival:
            print("MercadoPageContent.Compare: {}: JORNADA:  ({})!".format(otherData.source,
                                                                       cambRival))

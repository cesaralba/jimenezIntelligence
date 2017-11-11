from bs4 import BeautifulSoup as BS
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

        soup = BS(textPage['data'], "html.parser")
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

                # print(result)







                    # print("Player {} ->  {}".format(id, val))
                # print(player_data)




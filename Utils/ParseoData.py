import logging
import re
from typing import Optional, Any, List

import bs4
import pandas as pd
from CAPcore.Misc import onlySetElement, extractREGroups, BadString
from CAPcore.Web import mergeURL
from bs4 import NavigableString

from SMACB.Constants import URLIMG2IGNORE, DEFTZ
from .FechaHora import PATRONFECHA


def extractPlantillaInfoDiv(divData: bs4.BeautifulSoup, claseEntrada: str) -> dict:
    auxResult = {}
    dataFields = splitDiv(divData)

    if claseEntrada == 'jugadores':
        # For some reason Iss 256, age of a player wasn't included this is completely adhoc (that's life)
        if len(dataFields) == 3 and 'años' not in dataFields[2]:
            logging.error("Added missing data for player len data: %i, '%s'", len(dataFields), dataFields)

            newDataFields = dataFields[:2] + [None] + dataFields[2:]
            dataFields = newDataFields

        # los datos son ['1,93 m', 'EE.UU.', '29 años', 'EXT']
        auxResult['altura'] = parseaAltura(dataFields[0].strip())
        auxResult['nacionalidad'] = dataFields[1].strip()
        auxLicencia = dataFields[3].strip()
        auxLicenciaList = auxLicencia.split(" | ", maxsplit=1)
        auxResult['licencia'] = auxLicenciaList[0]
        auxResult['junior'] = len(auxLicenciaList) > 1
    elif claseEntrada == 'tecnicos':
        auxResult['nacionalidad'] = dataFields[0].strip()
    else:
        raise ValueError(f"Unknown claseEntrada '{claseEntrada}'")

    result = {k: v for k, v in auxResult.items() if v is not None}
    return result


def splitDiv(divData: bs4.BeautifulSoup) -> List[str]:
    result = [t.get_text() for t in divData.descendants if isinstance(t, NavigableString)]

    return result


def parseaAltura(data: str) -> Optional[int]:
    REaltura = r'^(\d)[,.](\d{2})\s*m$'
    result = None

    reProc = re.match(REaltura, data)
    if reProc:
        result = 100 * int(reProc.group(1)) + int(reProc.group(2))
    else:
        print(f"ALTURA '{data}' no casa RE '{REaltura}'")

    return result


def parseFecha(data: str) -> Optional[Any]:
    REfechaNac = r'^(?P<fechanac>\d{2}/\d{2}/\d{4})\s*.*'
    result = None

    reProc = re.match(REfechaNac, data)
    if reProc:
        result = pd.to_datetime(reProc['fechanac'], format=PATRONFECHA).tz_localize(DEFTZ)
    else:
        print("FECHANAC no casa RE", data, REfechaNac)

    return result


def ProcesaTiempo(cadena):
    reTiempo = r"^\s*(\d+):(\d+)\s*$"
    auxTemp = extractREGroups(cadena=cadena, regex=reTiempo)
    if auxTemp:
        return int(auxTemp[0]) * 60 + int(auxTemp[1])

    raise BadString(f"ProcesaEstadisticas:ProcesaTiempo '{cadena}' no casa RE '{reTiempo}'")


def findLocucionNombre(data: bs4.BeautifulSoup) -> dict:
    result = {}

    for scr in data.findAll('script'):
        dataText = scr.getText()
        if 'new Audio' not in dataText:
            continue
        PATaudio = r".*new Audio\('(?P<url>[^']+)'\).*"
        match = re.match(PATaudio, dataText.replace('\n', ''), re.MULTILINE)

        if match:
            url = match.group('url')
            result['audioURL'] = url
            break
        print(f"No RE '{PATaudio}'")

    return result


COPIAVERBATIM = {'posicion', 'licencia', 'lugar_nacimiento', 'nacionalidad'}
CLASS2KEY = {'lugar_nacimiento': 'lugarNac'}
CLASS2SKIP = {'equipo', 'dorsal'}


def procesaCosasUtilesPlantilla(data: bs4.BeautifulSoup, urlRef: str):
    result = {}
    result['sinDatos'] = False
    auxFoto = data.find('div', attrs={'class': 'foto'}).find('img')['src']
    if auxFoto not in URLIMG2IGNORE:
        result['urlFoto'] = mergeURL(urlRef, auxFoto)
    result['alias'] = data.find('h1').get_text().strip()
    for row in data.findAll('div', {'class': ['datos_basicos', 'datos_secundarios']}):

        valor = row.find("span", {'class': 'roboto_condensed_bold'}).get_text().strip()
        classDiv = row.attrs['class']

        if CLASS2SKIP.intersection(classDiv):
            continue
        if COPIAVERBATIM.intersection(classDiv):
            clavesSet = COPIAVERBATIM.intersection(classDiv)
            clave = onlySetElement(clavesSet)
            result[CLASS2KEY.get(clave, clave)] = valor
        elif 'altura' in classDiv:
            result['altura'] = parseaAltura(valor)
        elif 'fecha_nacimiento' in classDiv:
            result['fechaNac'] = parseFecha(valor)
        else:
            if 'Nombre completo:' in row.get_text():
                result['nombre'] = valor
            else:
                print("Fila no casa categorías conocidas", row)
    return result

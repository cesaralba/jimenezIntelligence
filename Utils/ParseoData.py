import logging
import re
from typing import Optional, Any

import pandas as pd
from bs4 import NavigableString

from .FechaHora import PATRONFECHA


def extractPlantillaInfoDiv(divData, claseEntrada) -> dict:
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


def splitDiv(divData):
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
        result = pd.to_datetime(reProc['fechanac'], format=PATRONFECHA)
    else:
        print("FECHANAC no casa RE", data, REfechaNac)

    return result

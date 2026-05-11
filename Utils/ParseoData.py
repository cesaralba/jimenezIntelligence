import re
from typing import Optional, Any, List

import bs4
import pandas as pd
from CAPcore.Misc import extractREGroups, BadString
from bs4 import NavigableString

from SMACB.Constants import DEFTZ
from .FechaHora import PATRONFECHA, PATRONFECHAGUI


def splitDiv(divData: bs4.BeautifulSoup) -> List[str]:
    result = [t.get_text() for t in divData.descendants if isinstance(t, NavigableString)]

    return result


def parseaAltura(data: str) -> Optional[int]:
    REaltura = r'^(\d)[,.](\d{2})\s*m?$'
    result = None

    reProc = re.match(REaltura, data)
    if reProc:
        result = 100 * int(reProc.group(1)) + int(reProc.group(2))
    else:
        print(f"ALTURA '{data}' no casa RE '{REaltura}'")

    return result


def parseFecha(data: str) -> Optional[Any]:
    REfechaNac = r'^(?P<fechanac>\d{2}[-/]\d{2}[/-]\d{4})\s*.*'
    result = None

    reProc = re.match(REfechaNac, data)
    if reProc:
        patronAusar = PATRONFECHA if ('/' in reProc['fechanac']) else PATRONFECHAGUI
        result = pd.to_datetime(reProc['fechanac'], format=patronAusar).tz_localize(DEFTZ)
    else:
        print("FECHANAC no casa RE", data, REfechaNac)

    return result


def ProcesaTiempo(cadena):
    reTiempo = r"^\s*(\d+):(\d+)\s*$"
    auxTemp = extractREGroups(cadena=cadena, regex=reTiempo)
    if auxTemp:
        return int(auxTemp[0]) * 60 + int(auxTemp[1])

    raise BadString(f"ProcesaEstadisticas:ProcesaTiempo '{cadena}' no casa RE '{reTiempo}'")

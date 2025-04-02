import re
import sys
from collections import namedtuple
from typing import Optional, List

import SMACB.Programa.Globals

tradEquipos = SMACB.Programa.Globals.tradEquipos


def listaEquipos(tempData, beQuiet=False):
    if beQuiet:
        print(" ".join(sorted(tradEquipos['c2n'])))
    else:
        print("Abreviatura -> nombre(s) equipo")
        for abr in sorted(tradEquipos['c2n']):
            listaEquiposAux = sorted(tradEquipos['c2n'][abr], key=lambda x: (len(x), x), reverse=True)
            listaEquiposStr = ",".join(listaEquiposAux)
            print(f'{abr}: {listaEquiposStr}')

    sys.exit(0)


def preparaListaTablas(paramTablas: str) -> Optional[List[str]]:
    tablaKey = namedtuple('tablaKey', ['clave', 'ayuda'])
    paramTabla2key = {'tot': tablaKey('TOTALES', 'Totales de los jugadores'),
                      'prom': tablaKey('PROMEDIOS', 'Promedios de los jugadores'),
                      'ultpar': tablaKey('ULTIMOPARTIDO', 'Ultimo partido de los jugadores con el equipo')}

    result = []

    if paramTablas.lower().strip() == "no":
        return []

    PATsepList = r'[ ,]+'

    auxList = list(map(lambda s: s.strip().lower(), re.split(PATsepList, paramTablas)))

    extraTablas = set(auxList).difference(paramTabla2key.keys())
    if extraTablas:
        if 'no' in extraTablas:
            print(f" 'no' debe ir sólo. Parámetros: '{paramTablas}'")
        else:
            print(f"Tablas desconocidas en parámetro 'tablasjugs': {','.join(extraTablas)}. Suministrado: '"
                  f"{paramTablas}'. Validas: {sorted(paramTabla2key.keys())} ")
        return None

    usedKeys = set()
    for par in auxList:
        if par in usedKeys:
            continue
        usedKeys.add(par)
        result.append(paramTabla2key[par].clave)

    return result

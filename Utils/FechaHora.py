import re
from collections import namedtuple
from copy import deepcopy
from datetime import datetime

import numpy as np
import pandas as pd
from CAPcore.Misc import FORMATOtimestamp

from SMACB.Constants import DEFTZ

PATRONFECHAHORA = "%d/%m/%Y %H:%M"
PATRONFECHA = "%d/%m/%Y"
NEVER = pd.to_datetime("2040-12-31 00:00")

Age = namedtuple('Age', ['delta', 'years', 'meses', 'dias', 'doys'])


def time2Str(timeref):
    """
    Returns a str with DATE - TIME if time of day isn't 00:00 (0:00 could be read as TBD)
    :param timeref:
    :return:
    """
    formatStr = "%d-%m-%Y" if (timeref.hour == 0 and timeref.min == 0) else "%d-%m-%Y %H:%M"

    result = timeref.strftime(formatStr)

    return result


def prevBirthday(datebirth, dateref):
    diffyear = -1 if (dateref.month, dateref.day) < (datebirth.month, datebirth.day) else 0  # It was year before

    fechaCump = f'{dateref.year + diffyear: 4}-{datebirth.month: 2}-{datebirth.day: 2}'
    result = pd.to_datetime(fechaCump).tz_localize(DEFTZ)

    return result


def calcAge(datebirth, dateref=None):
    """Calcula la edad. La cuenta de meses días, falla en el caso de bisiestos"""
    if dateref is None:
        dateref = pd.to_datetime("today").tz_localize(DEFTZ)

    datenac = datebirth.date()
    dateref = dateref.date()
    cumple = prevBirthday(datebirth=datenac, dateref=dateref).date()

    auxdiffyear = -1 if (dateref.month, dateref.day) < (datebirth.month, datebirth.day) else 0
    yeardiff = dateref.year - datebirth.year + auxdiffyear

    auxDate = pd.Timedelta(dateref - datenac)

    edadAux = {'delta': (dateref - datenac), 'years': yeardiff, 'meses': int(auxDate // np.timedelta64(1, 'M')) % 12,
               'dias': int((auxDate % np.timedelta64(1, 'M')).days), 'doys': int((dateref - cumple).days)}

    return Age(**edadAux)


def fechaParametro2pddatetime(fecha) -> pd.Timestamp:
    """
    Convierte una cadena a Timestamp (el parse de pandas es muy flexible)
    :param fecha:
    :return:
    """
    result = fecha if isinstance(fecha, pd.Timestamp) else pd.to_datetime(fecha).tz_localize(DEFTZ)

    return result


def secs2TimeStr(x):
    """
    Converts number of seconds to a string MM:SS
    :param x:
    :return:
    """
    mins = x // 60
    secs = x % 60

    result = f"{mins:.0f}" ":" f"{secs:02.0f}"

    return result


def fecha2fechaCalDif(d: pd.Timestamp) -> str:
    """
    Convierte la fecha del partido en una cadena (para la comparación de calendario)
    :param d: fecha a comparar
    :return: fecha formateada (el formato depende del valor del parámetro)
    """
    if d == NEVER:
        return "TBD"
    result = f"{time2Str(d)} ({d.strftime('%a')})"
    return result


def procesaFechasJornada(cadFechas):
    resultado = {}

    mes2n = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10,
             'nov': 11, 'dic': 12}

    patronBloqueFechas = r'^(?P<dias>\d{1,2}(-\d{1,2})*)\s+(?P<mes>\w+)\s+(?P<year>\d{4})$'

    bloques = []
    cadWrk = cadFechas.lower().strip()

    for bY in cadWrk.split(' y '):
        for b in bY.strip().split(','):
            bloques.append(b.strip())

    for b in bloques:
        reFecha = re.match(patronBloqueFechas, b.strip())
        if reFecha:
            yearN = int(reFecha['year'].strip())
            for d in reFecha['dias'].split("-"):
                diaN = int(d.strip())
                cadResult = f"{yearN:04d}-{mes2n[reFecha['mes']]:02d}-{diaN:02d}"
                if diaN in resultado:
                    resultado[diaN].add(cadResult)
                else:
                    resultado[diaN] = {cadResult}
        else:
            raise ValueError(f"procesaFechasJornada: {cadFechas} RE: '{b}' no casa patrón '{patronBloqueFechas}'")

    return resultado


def procesaFechaHoraPartido(cadFecha, cadHora, datosCab):
    resultado = NEVER
    # diaSem2n = {'lun': 0, 'mar': 1, 'mié': 2, 'jue': 3, 'vie': 4, 'sáb': 5, 'dom': 6}
    patronDiaPartido = r'^(?P<diasem>\w+)\s(?P<diames>\d{1,2})$'

    reFechaPart = re.match(patronDiaPartido, cadFecha.strip())

    if reFechaPart:
        if cadHora is None:
            cadHora = "00:00"
        # diaSemN = diaSem2n[reFechaPart['diasem']]
        diaMesN = int(reFechaPart['diames'])

        auxFechasN = deepcopy(datosCab['auxFechas'])[diaMesN]

        if len(auxFechasN) > 1:
            pass  # Caso tratado en destino
        else:
            cadFechaFin = auxFechasN.pop()
            cadMezclada = f"{cadFechaFin.strip()} {cadHora.strip()}"
            try:
                fechaPart = pd.to_datetime(cadMezclada).tz_localize(DEFTZ)
                resultado = fechaPart
            except ValueError:
                print(f"procesaFechaHoraPartido: '{cadFechaFin}' no casa RE '{FORMATOtimestamp}'")
                resultado = NEVER

    else:
        raise ValueError(f"RE: '{cadFecha}' no casa patrón '{patronDiaPartido}'")

    return resultado


def procesaFechaJornada(cadFecha: str) -> datetime:
    mes2n = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
             'septiembre': 9, 'octubre': 10,
             'noviembre': 11, 'diciembre': 12}

    patronBloqueFecha = r'^(?P<dia>\d{1,2})\s+de\s+(?P<mes>\w+)\s+de\s+(?P<year>\d{4})$'

    reFecha = re.match(patronBloqueFecha, cadFecha.lower().strip())
    if reFecha:
        yearN = int(reFecha['year'].strip())
        diaN = int(reFecha['dia'].strip())
        mesN = mes2n[reFecha['mes']]
        resultado = datetime(year=yearN, month=mesN, day=diaN)
    else:
        raise ValueError(f"procesaFechasJornada: RE: '{cadFecha}' no casa patrón '{patronBloqueFecha}'")

    return resultado

from collections import namedtuple

import numpy as np
import pandas as pd
from time import struct_time, strftime

PATRONFECHAHORA = "%d/%m/%Y %H:%M"
PATRONFECHA = "%d/%m/%Y"
NEVER = pd.to_datetime("2030-12-31 00:00")

Edad = namedtuple('Edad', ['delta', 'years', 'meses', 'dias', 'doys'])


def Time2Str(timeref: struct_time):
    """
    Vuelca estructura de fecha con hora (si es distinta de 0:00). Ok, no es genérica pero aún no hay partidos ACB a
    media noche
    :param timeref:
    :return:
    """
    format = "%d-%m-%Y" if (timeref.tm_hour == 0 and timeref.tm_min == 0) else "%d-%m-%Y %H:%M"

    result = strftime(format, timeref)

    return result


def CumplePrevio(fechanac, fecharef):
    diffyear = -1 if (fecharef.month, fecharef.day) < (fechanac.month, fechanac.day) else 0  # Es el del año anterior

    fechaCump = f'{fecharef.year + diffyear:4}-{fechanac.month:2}-{fechanac.day:2}'
    result = pd.to_datetime(fechaCump)

    return result


def CalcEdad(fechanac, fecharef=None):
    """Calcula la edad. La cuenta de meses días, falla en el caso de bisiestos"""
    if fecharef is None:
        fecharef = pd.to_datetime("today")

    datenac = fechanac.date()
    dateref = fecharef.date()
    cumple = CumplePrevio(fechanac=datenac, fecharef=dateref).date()

    auxdiffyear = -1 if (fecharef.month, fecharef.day) < (fechanac.month, fechanac.day) else 0
    yeardiff = fecharef.year - fechanac.year + auxdiffyear

    auxDate = pd.Timedelta(dateref - datenac)

    edadAux = {'delta': (dateref - datenac),
               'years': yeardiff,
               'meses': int(auxDate // np.timedelta64(1, 'M')) % 12,
               'dias': int((auxDate % np.timedelta64(1, 'M')).days),
               'doys': int((dateref - cumple).days)}

    return Edad(**edadAux)

from collections import namedtuple

import numpy as np
import pandas as pd

PATRONFECHAHORA = "%d/%m/%Y %H:%M"
PATRONFECHA = "%d/%m/%Y"
NEVER = pd.to_datetime("2030-12-31 00:00")

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
    result = pd.to_datetime(fechaCump)

    return result


def calcAge(datebirth, dateref=None):
    """Calcula la edad. La cuenta de meses días, falla en el caso de bisiestos"""
    if dateref is None:
        dateref = pd.to_datetime("today")

    datenac = datebirth.date()
    dateref = dateref.date()
    cumple = prevBirthday(datebirth=datenac, dateref=dateref).date()

    auxdiffyear = -1 if (dateref.month, dateref.day) < (datebirth.month, datebirth.day) else 0
    yeardiff = dateref.year - datebirth.year + auxdiffyear

    auxDate = pd.Timedelta(dateref - datenac)

    edadAux = {'delta': (dateref - datenac), 'years': yeardiff, 'meses': int(auxDate // np.timedelta64(1, 'M')) % 12,
               'dias': int((auxDate % np.timedelta64(1, 'M')).days), 'doys': int((dateref - cumple).days)}

    return Age(**edadAux)


def fechaParametro2pddatetime(fecha):
    result = fecha if isinstance(fecha, pd.Timestamp) else pd.to_datetime(fecha)
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

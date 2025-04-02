from math import isnan
from typing import Set

import pandas as pd

from SMACB import TemporadaACB as TempACB
from SMACB.Constants import infoClasifEquipo, local2espLargo, LocalVisitante, haGanado2esp
from SMACB.TemporadaACB import TemporadaACB
from Utils.FechaHora import NEVER, secs2TimeStr


def auxCalculaBalanceStrSuf(record: infoClasifEquipo, addPendientes: bool = False, currJornada: int = None,
                            addPendJornada: bool = False, jornadasCompletas: Set[int] = None       ) -> str:
    if jornadasCompletas is None:
        jornadasCompletas = set()

    textoAux = ""
    if currJornada is not None:
        pendJornada = currJornada not in record.Jjug
        pendientes = [p for p in range(1, currJornada) if p not in record.Jjug]
        adelantados = [p for p in record.Jjug if (p > currJornada) and (p not in jornadasCompletas)]
        textoAux = ("" + ("J" if (pendJornada and addPendJornada) else "") + ("P" * len(pendientes)) + (
                "A" * len(adelantados)))

    strPendiente = f" ({textoAux})" if (addPendientes and textoAux) else ""

    return strPendiente


def auxCalculaBalanceStr(record: infoClasifEquipo, addPendientes: bool = False, currJornada: int = None,
                         addPendJornada: bool = False, jornadasCompletas: Set[int] = None
                         ) -> str:
    strPendiente = auxCalculaBalanceStrSuf(record, addPendientes, currJornada, addPendJornada, jornadasCompletas)
    victorias = record.V
    derrotas = record.D
    texto = f"{victorias}-{derrotas}{strPendiente}"

    return texto


def auxCalculaFirstBalNeg(clasif: list[infoClasifEquipo]):
    for posic, eq in enumerate(clasif):
        victs = eq.V
        derrs = eq.D

        if derrs > victs:
            return posic + 1
    return None


def partidoTrayectoria(partido: TempACB.filaTrayectoriaEq, datosTemp: TemporadaACB):
    datoFecha = partido.fechaPartido
    strFecha = partido.fechaPartido.strftime(FMTECHACORTA) if datoFecha != NEVER else "TBD"
    etiqLoc = "vs " if partido.esLocal else "@"
    nombrRival = partido.equipoRival.nombcorto
    abrevRival = partido.equipoRival.abrev
    textRival = f"{etiqLoc}{nombrRival}"
    strRival = f"{strFecha}: {textRival}"

    strResultado = None
    if not partido.pendiente:
        clasifAux = datosTemp.clasifEquipo(abrevRival, datoFecha)
        clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=int(partido.jornada),
                                         addPendJornada=False)
        strRival = f"{strFecha}: {textRival} ({clasifStr})"
        marcador = partido.resultado._asdict()
        locEq = local2espLargo[partido.esLocal]
        locGanador = local2espLargo[partido.esLocal and partido.haGanado]
        for loc in LocalVisitante:
            marcador[loc] = str(marcador[loc])
            if loc == locGanador:
                marcador[loc] = f"<b>{marcador[loc]}</b>"
            if loc == locEq:
                marcador[loc] = f"<u>{marcador[loc]}</u>"

        resAux = [marcador[loc] for loc in LocalVisitante]
        strResultado = f"{'-'.join(resAux)} ({haGanado2esp[partido.haGanado]})"
    return strRival, strResultado


def GENERADORETTIRO(*kargs, **kwargs):
    return lambda f: auxEtiqTiros(f, *kargs, **kwargs)


def GENERADORETREBOTE(*kargs, **kwargs):
    return lambda f: auxEtiqRebotes(f, *kargs, **kwargs)


def GENERADORFECHA(*kargs, **kwargs):
    return lambda f: auxEtFecha(f, *kargs, **kwargs)


def GENERADORTIEMPO(*kargs, **kwargs):
    return lambda f: auxEtiqTiempo(f, *kargs, **kwargs)


def GENMAPDICT(*kargs, **kwargs):
    return lambda f: auxMapDict(f, *kargs, **kwargs)


def GENERADORCLAVEDORSAL(*kargs, **kwargs):
    return lambda f: auxKeyDorsal(f, *kargs, **kwargs)


def auxEtiqRebotes(df, entero: bool = True) -> str:
    if isnan(df['R-D']):
        return "-"

    formato = "{:3}+{:3} {:3}" if entero else "{:5.1f}+{:5.1f} {:5.1f}"

    valores = [int(v) if entero else v for v in [df['R-D'], df['R-O'], df['REB-T']]]

    result = formato.format(*valores)

    return result


def auxEtiqTiempo(df, col='Segs'):
    t = df[col]
    if isnan(t):
        return "-"

    return secs2TimeStr(t)


def auxEtiqTiros(df, tiro, entero=True):
    formato = "{:3}/{:3} {:5.1f}%" if entero else "{:5.1f}/{:5.1f} {:5.1f}%"

    etTC = f"T{tiro}-C"
    etTI = f"T{tiro}-I"
    etTpc = f"T{tiro}%"

    if df[etTI] == 0.0 or isnan(df[etTI]):
        return "-"

    valores = [int(v) if entero else v for v in [df[etTC], df[etTI]]] + [df[etTpc]]

    result = formato.format(*valores)

    return result


FMTECHACORTA = "%d-%m"


def auxEtFecha(f, col, formato=FMTECHACORTA):
    if f is None:
        return "-"

    dato = f[col]
    result = "-" if pd.isnull(dato) else dato.strftime(formato)

    return result


def auxMapDict(f, col, lookup):
    if f is None:
        return "-"

    dato = f[col]
    result = lookup.get(dato, "-")

    return result


def auxKeyDorsal(f, col):
    if f is None:
        return "-"

    dato = f[col]

    try:
        auxResult = int(dato)
    except ValueError:
        auxResult = 999

    result = -1 if dato == "00" else auxResult

    return result


def auxJugsBajaTablaJugs(datos: pd.DataFrame, colActivo=('Jugador', 'Activo')) -> list[int]:
    """
    Devuelve las filas con jugadores que figuran como dados de baja (para ser más preciso, no como Alta)
    :param datos: dataframe con datos para tabla de jugadores
    :param colActivo: columna que contiene si el jugador está activo
    :return: lista con las filas del dataframe (comienza en 0) con jugadores así
    """
    result = []

    # No hay datos
    if colActivo not in datos.columns:
        return result

    estadoJugs = datos[colActivo]

    # Si son todos de baja, nos da igual señalar
    if all(estadoJugs) or all(not x for x in estadoJugs):
        return result

    result = [i for i, estado in enumerate(list(estadoJugs)) if not estado]

    return result


def auxBold(data):
    return f"<b>{data}</b>"

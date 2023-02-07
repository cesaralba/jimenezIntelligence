from itertools import product

import pandas as pd

from SMACB.Constants import LocalVisitante, EqRival
from SMACB.TemporadaACB import TemporadaACB

COLFECHAPARTIDO = ('Info', 'fechaPartido')
ABREVPAIRS = {'LV': LocalVisitante, 'ER': EqRival}

COLSINFO4STATS = [('Info', 'VictoriaLocal'), ('Info', 'Ptot'), ('Info', 'Ftot'), ('Info', 'POStot'),
                  ('Info', 'ratio40min')]

COLSSTATEQ4STATS = ['haGanado', 'convocados', 'utilizados', 'Segs', 'P', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%',
                    'T1-C', 'T1-I', 'T1%', 'REB-T', 'R-D', 'R-O', 'A', 'BR', 'BP', 'TAP-F', 'TAP-C', 'FP-F', 'FP-C',
                    'TC-I', 'TC-C', 'TC%', 'POS', 'OER', 'OERpot', 'EffRebD', 'EffRebO', 't2/tc-I', 't3/tc-I',
                    't2/tc-C', 't3/tc-C', 'eff-t2', 'eff-t3', 'ppTC', 'A/TC-C', 'A/BP', 'RO/TC-F', 'P_por40m',
                    'T2-C_por40m', 'T2-I_por40m', 'T3-C_por40m', 'T3-I_por40m', 'T1-C_por40m', 'T1-I_por40m',
                    'REB-T_por40m', 'R-D_por40m', 'R-O_por40m', 'A_por40m', 'BR_por40m', 'BP_por40m', 'TAP-F_por40m',
                    'TAP-C_por40m', 'FP-F_por40m', 'FP-C_por40m', 'V_por40m', 'TC-I_por40m', 'TC-C_por40m',
                    'POS_por40m', 'P_porPos', 'T2-C_porPos', 'T2-I_porPos', 'T3-C_porPos', 'T3-I_porPos', 'A_porPos',
                    'BR_porPos', 'BP_porPos', 'TAP-F_porPos', 'TAP-C_porPos', 'FP-F_porPos', 'FP-C_porPos',
                    'TC-I_porPos', 'TC-C_porPos']


def dfPartidos2serieFechas(dfPartidos: pd.DataFrame, colFecha=COLFECHAPARTIDO, abrEq=None,
                           datosTemp: TemporadaACB = None):
    listaPartidos = dfPartidos
    if abrEq:
        if datosTemp is None:
            raise ValueError(
                f"dfPartidos2serieFechas: si se suministra abreviatura '{abrEq}' se requiere info de temporada")

        if not len(datosTemp.tradEquipos['c2i'][abrEq]):
            raise KeyError(f"dfPartidos2serieFechas: '{abrEq}' desconocida en temporada")

        idEq = list(datosTemp.tradEquipos['c2i'][abrEq])[0]
        listaPartidos = dfPartidos[teamMatch(dfPartidos, idEq, field='id', teamOnly=True)]

    if (colFecha in listaPartidos.columns):
        auxResult = pd.Series(listaPartidos[colFecha].unique())
    elif (colFecha in listaPartidos.index.names):
        if isinstance(listaPartidos.index, pd.Index):
            auxResult = pd.Series(listaPartidos.index.to_series().unique())
        elif isinstance(listaPartidos.index, pd.MultiIndex):
            auxResult = pd.Series(listaPartidos.index.to_frame(allow_duplicates=False))
        else:
            raise TypeError("dfPartidos2serieFechas: tipo desconocido de index")
    else:
        raise KeyError(f"dfPartidos2serieFechas: columna desconocida '{colFecha}'")

    result = auxResult.sort_values()
    return result


def preparaEstadisticas(partidosLV: pd.DataFrame):
    """
    ['local', 'id', 'RIVid', 'Nombre', 'RIVNombre', 'abrev', 'RIVabrev',
     'haGanado', 'convocados', 'utilizados', 'Segs', 'P', 'T2-C', 'T2-I',
     'T2%', 'T3-C', 'T3-I', 'T3%', 'T1-C', 'T1-I', 'T1%', 'REB-T', 'R-D',
     'R-O', 'A', 'BR', 'BP', 'C', 'TAP-F', 'TAP-C', 'M', 'FP-F', 'FP-C',
     '+/-', 'V', 'TC-I', 'TC-C', 'TC%', 'POS', 'OER', 'OERpot', 'EffRebD',
     'EffRebO', 't2/tc-I', 't3/tc-I', 't2/tc-C', 't3/tc-C', 'eff-t2',
     'eff-t3', 'ppTC', 'A/TC-C', 'A/BP', 'RO/TC-F']
       """
    COLSPARA40MIN = ['P', 'T2-C', 'T2-I', 'T3-C', 'T3-I', 'T1-C', 'T1-I', 'REB-T', 'R-D', 'R-O', 'A', 'BR', 'BP',
                     'TAP-F', 'TAP-C', 'FP-F', 'FP-C', 'V', 'TC-I', 'TC-C', 'POS']
    COLSPARAPOS = ['P', 'T2-C', 'T2-I', 'T3-C', 'T3-I', 'A', 'BR', 'BP', 'TAP-F', 'TAP-C', 'FP-F', 'FP-C', 'TC-I',
                   'TC-C']

    result = partidosLV.copy()
    for loc in LocalVisitante:
        for col in COLSPARA40MIN:
            result.loc[:, (loc, f"{col}_por40m")] = result[(loc, col)] * result[('Info', 'ratio40min')]
        for col in COLSPARAPOS:
            result.loc[:, (loc, f"{col}_porPos")] = result[(loc, col)] / result[(loc, 'POS')]

    return result


def df2KEYPAIR(df):
    field = 'abrev'
    for dfType, pairMain in ABREVPAIRS.items():
        pair = list(product(pairMain, [field]))

        if len(set(df.columns.to_list()).intersection(pair)) == len(pair):
            result = dfType
            break
    else:
        raise ValueError('df2KEYPAIR: tipo de df no reconocido')

    return result


def getAbrevPair(df: pd.DataFrame, field='abrev', teamOnly: bool = False):
    resultType = df2KEYPAIR(df)
    resultPair = list(product(ABREVPAIRS[resultType], [field]))
    result = [resultPair[0]] if (teamOnly and (resultType == 'ER')) else resultPair

    return result


def teamMatch(df, x, field='abrev', teamOnly=False):
    pairKeys = getAbrevPair(df, field=field, teamOnly=teamOnly)
    result = (df[pairKeys] == x).iloc[:, 0] if len(pairKeys) == 1 else (df[pairKeys] == x).any(axis=1)

    return result


def getMarkerMatch(df, abrev1, abrev2, fill=False, filler=''):
    result = pd.Series(index=df.index, dtype='object')
    result[teamMatch(df, abrev1)] = abrev1
    result[teamMatch(df, abrev2)] = abrev2
    result[(teamMatch(df, abrev1) & teamMatch(df, abrev2))] = 'prec'

    if fill:
        result = result.fillna(filler)
    return result


def calculaEstadisticosPartidos(dfPartidos: pd.DataFrame, campoFecha=COLFECHAPARTIDO, listafechas=None):
    dfKeyPair = df2KEYPAIR(dfPartidos)
    campos_STATS = COLSINFO4STATS + sorted(list(product(ABREVPAIRS[dfKeyPair], COLSSTATEQ4STATS)))
    if campoFecha is not None and (campoFecha not in dfPartidos.columns) and (campoFecha not in dfPartidos.index.names):
        raise KeyError(f"calculaEstadisticosPartidos: la clave {campoFecha} no está en las columnas del DF")

    if campoFecha in dfPartidos.columns:
        fechasRef = dfPartidos[campoFecha]
    elif campoFecha in dfPartidos.index.names:
        if isinstance(dfPartidos.index, pd.MultiIndex):
            fechasRef = dfPartidos.index.to_frame(allow_duplicates=True)[campoFecha]
        elif isinstance(dfPartidos.index, pd.Index):
            fechasRef = dfPartidos.index.to_series()
        else:
            raise TypeError("dfPartidos2serieFechas: tipo desconocido de index")

    fechasWork = listafechas if (listafechas is not None) else dfPartidos2serieFechas(dfPartidos, colFecha=campoFecha)

    auxResult = []
    for t in fechasWork:
        newRow = dfPartidos[fechasRef <= t][campos_STATS].describe(percentiles=[0.5]).unstack().T

        auxResult.append(newRow)

    result = pd.DataFrame(data=auxResult, index=fechasWork)

    return result

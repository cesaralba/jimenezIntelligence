import numpy as np

import pandas as pd

from SMACB.Constants import LocalVisitante
from SMACB.TemporadaACB import TemporadaACB

COLFECHAPARTIDO=('Info','fechaPartido')

def dfPartidos2serieFechas(dfPartidos: pd.DataFrame, colFecha=COLFECHAPARTIDO, abrEq=None, datosTemp: TemporadaACB=None):
    listaPartidos = dfPartidos
    if abrEq:
        if datosTemp is None:
            raise ValueError(f"dfPartidos2serieFechas: si se suministra abreviatura '{abrEq}' se requiere info de temporada")

        if  not len(datosTemp.tradEquipos['c2i'][abrEq]):
            raise KeyError(f"dfPartidos2serieFechas: '{abrEq}' desconocida en temporada")

        idEq = list(datosTemp.tradEquipos['c2i'][abrEq])[0]
        listaPartidos = dfPartidos[teamMatch(dfPartidos,abrEq)]

    if (colFecha in dfPartidos.columns):
        result = listaPartidos[colFecha].unique()
    elif (colFecha in dfPartidos.index.names):
        if isinstance(dfPartidos.index,pd.Index):
            result = dfPartidos.index.to_series().unique()
        elif isinstance(dfPartidos.index,pd.MultiIndex):
            result = dfPartidos.index.to_frame(allow_duplicates=False)
        else:
            raise TypeError("dfPartidos2serieFechas: tipo desconocido de index")
    else:
        raise KeyError(f"dfPartidos2serieFechas: columna desconocida '{colFecha}'")

    result.sort()

    return pd.Series(result)


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


def getAbrevPair(df: pd.DataFrame):
    if (('Local','abrev') in df.columns) and (('Visitante','abrev') in df.columns):
        return [('Local','abrev'),('Visitante','abrev')]
    elif (('Eq','abrev') in df.columns) and (('Rival','abrev') in df.columns):
        return [('Eq','abrev'),('Rival','abrev')]
    else:
        raise ValueError('getAbrevPair: tipo no reconocido')


def teamMatch(df,abrev):
    pairKeys = getAbrevPair(df)
    result=(df[pairKeys]==abrev).any(axis=1)
    return result

def getMarkerMatch(df,abrev1,abrev2,fill=False,filler=''):
    result=pd.Series(index=df.index,dtype='object')
    result[teamMatch(df,abrev1)]=abrev1
    result[teamMatch(df,abrev2)]=abrev2
    result[(teamMatch(df,abrev1)&teamMatch(df,abrev2))]='prec'

    if fill:
        result=result.fillna(filler)
    return result


def calculaEstadisticosPartidos(dfPartidos: pd.DataFrame,campoFecha=COLFECHAPARTIDO,listafechas=None):

    if campoFecha is not None and (campoFecha not in dfPartidos.columns) and (campoFecha not in dfPartidos.index.names):
        raise KeyError(f"calculaEstadisticosPartidos: la clave {campoFecha} no está en las columnas del DF")

    if campoFecha in dfPartidos.columns:
        fechasRef = dfPartidos[[campoFecha]]
    elif campoFecha in dfPartidos.index.names:
        if isinstance(dfPartidos.index,pd.Index):
            fechasRef = dfPartidos.index.to_series()
        elif isinstance(dfPartidos.index,pd.MultiIndex):
            fechasRef = dfPartidos.index.to_frame(allow_duplicates=True)[[campoFecha]]
        else:
            raise TypeError("dfPartidos2serieFechas: tipo desconocido de index")

    fechasWork = listafechas if (listafechas is not None) else dfPartidos2serieFechas(dfPartidos, colFecha=campoFecha)

    auxResult = []
    for t in fechasWork:
        newRow = dfPartidos[fechasRef<=t].describe(percentiles=[0.5]).unstack().T

        auxResult.append(newRow)

    result = pd.DataFrame(data=auxResult,index=fechasWork)

    return result

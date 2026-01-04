import numpy as np
import pandas as pd
from CAPcore.Misc import iterable2quotedString

from Utils.Pandas import combinaPDindexes


def extraeCampoYorden(estads: pd.DataFrame, estadsOrden: pd.DataFrame, eq: str = 'eq', clave: str = 'P',
                      estadistico='mean'):
    targetCol = (eq, clave, estadistico)

    if targetCol not in estads.index:
        valCorrectos = iterable2quotedString(estads.index, charQuote="")
        raise KeyError(f"extraeCampoYorden: parametros para dato '{targetCol}' desconocidos. Referencias válidas: "
                       f"{valCorrectos}")

    valor = estads.loc[targetCol]
    orden = estadsOrden.loc[targetCol]

    return valor, orden


def auxCalculaEstadsSubDataframe(dfEntrada: pd.DataFrame):
    FILASESTADISTICOS = ['count', 'mean', 'std', 'min', '50%', 'max']
    ROWRENAMER = {'50%': 'median'}

    estadisticosNumber = dfEntrada.describe(include=[np.number], percentiles=[.50])
    # Necesario porque describe trata los bool como categóricos
    estadisticosBool = dfEntrada.select_dtypes([np.bool_]).astype(np.int64).apply(
        lambda c: c.describe(percentiles=[.50]))

    auxEstadisticos = pd.concat([estadisticosNumber, estadisticosBool], axis=1).T[FILASESTADISTICOS].T

    # Hay determinados campos que no tiene sentido sumar. Así que sumamos todos y luego ponemos a nan los que no
    # Para estos tengo dudas filosóficas de cómo calcular la media (¿media del valor de cada partido o calcular el
    # ratio a partir de las sumas?
    sumas = dfEntrada[auxEstadisticos.columns].select_dtypes([np.number, np.bool_]).sum()

    sumasDF = pd.DataFrame(sumas).T
    sumasDF.index = pd.Index(['sum'])

    finalDF = pd.concat([auxEstadisticos, sumasDF]).rename(index=ROWRENAMER)

    result = finalDF.unstack()

    return result


def calculaTempStats(datos, clave, filtroFechas=None):
    if clave not in datos:
        raise KeyError(f"Clave '{clave}' no está en datos.")

    datosWrk = datos
    if filtroFechas:  # TODO: Qué hacer con el filtro
        datosWrk = datos

    agg = datosWrk.set_index('codigo')[clave].astype('float64').groupby('codigo').agg(
        ['mean', 'std', 'count', 'median', 'min', 'max', 'skew'])
    agg1 = agg.rename(columns={x: (clave + "-" + x) for x in agg.columns}).reset_index()
    return agg1


def calculaZ(datos, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    finalKeys = ['codigo', 'competicion', 'temporada', 'jornada', 'CODequipo', 'CODrival', 'esLocal', 'haJugado',
                 'fechaPartido', 'periodo', clave]
    finalTypes = {'CODrival': 'category', 'esLocal': 'bool', 'CODequipo': 'category', ('half-' + clave): 'bool',
                  ('aboveAvg-' + clave): 'bool', (clZ + '-' + clave): 'float64'}
    # We already merged SuperManager?
    if 'pos' in datos.columns:
        finalKeys.append('pos')
        finalTypes['pos'] = 'category'

    datosWrk = datos
    if filtroFechas:
        datosWrk = datos  # TODO: filtro de fechas

    agg1 = calculaTempStats(datos, clave, filtroFechas)

    dfResult = datosWrk[finalKeys].merge(agg1)
    stdMult = (1 / dfResult[clave + "-std"]) if useStd else 1
    dfResult[clZ + '-' + clave] = (dfResult[clave] - dfResult[clave + "-mean"]) * stdMult
    dfResult['half-' + clave] = (((dfResult[clave] - dfResult[clave + "-median"]) > 0.0)[~dfResult[clave].isna()]) * 100
    dfResult['aboveAvg-' + clave] = ((dfResult[clZ + '-' + clave] >= 0.0)[~dfResult[clave].isna()]) * 100

    return dfResult.astype(finalTypes)


def calculaVars(temporada, clave, useStd=True, filtroFechas=None):
    clZ = 'Z' if useStd else 'D'

    combs = {'R': ['CODrival'], 'RL': ['CODrival', 'esLocal'], 'L': ['esLocal']}
    if 'pos' in temporada.columns:
        combs['RP'] = ['CODrival', 'pos']
        combs['RPL'] = ['CODrival', 'esLocal', 'pos']

    colAdpt = {('half-' + clave + '-mean'): (clave + '-mejorMitad'),
               ('aboveAvg-' + clave + '-mean'): (clave + '-sobreMedia')}
    datos = calculaZ(temporada, clave, useStd=useStd, filtroFechas=filtroFechas)
    result = {}

    for combN, combV in combs.items():
        combfloat = combV + [(clZ + '-' + clave)]
        resfloat = datos[combfloat].groupby(combV).agg(['mean', 'std', 'count', 'min', 'median', 'max', 'skew'])
        combbool = combV + [('half-' + clave), ('aboveAvg-' + clave)]
        resbool = datos[combbool].groupby(combV).agg(['mean'])
        result[combN] = pd.concat([resbool, resfloat], axis=1, sort=True).reset_index()
        result[combN].columns = [((combN + "-" + colAdpt.get(x, x)) if clave in x else x) for x in
                                 combinaPDindexes(result[combN].columns)]
        result[combN]["-".join([combN, clave, (clZ.lower() + "Min")])] = (
                result[combN]["-".join([combN, clZ, clave, 'mean'])] -
                result[combN]["-".join([combN, clZ, clave, 'std'])])
        result[combN]["-".join([combN, clave, (clZ.lower() + "Max")])] = (
                result[combN]["-".join([combN, clZ, clave, 'mean'])] +
                result[combN]["-".join([combN, clZ, clave, 'std'])])

    return result

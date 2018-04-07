'''
Created on Apr 1, 2018

@author: calba
'''

from SMACB.TemporadaACB import calculaTempStats, calculaVars


def calculaDFconVars(dfTemp, dfMerc, clave, useStd=True, filtroFechas=None):
    dfVars = calculaVars(dfTemp, clave=clave, useStd=useStd, filtroFechas=filtroFechas)
    dfTempEstats = calculaTempStats(dfTemp, clave=clave, filtroFechas=filtroFechas)

    dfResult = dfMerc.copy().merge(dfTempEstats)

    for comb in dfVars:
        claveZmin = "-".join([comb, clave, "zMin"])
        claveZmax = "-".join([comb, clave, "zMax"])
        # claveZmean = "-".join([comb,"Z",clave,"mean"])
        # claveZstd = "-".join([comb,"Z",clave,"std"])

        claveVmean = "-".join([clave, "mean"])
        claveVstd = "-".join([clave, "std"])
        clavePrmin = "-".join([comb, clave, "predMin"])
        clavePrmax = "-".join([comb, clave, "predMax"])
        #  'RP-V-mejorMitad', 'RP-V-sobreMedia', 'RP-Z-V-mean', 'RP-Z-V-std', 'RP-Z-V-count'
        claveProbAbove = "-".join([comb, clave, "sobreMedia"])
        claveProbMejorMitad = "-".join([comb, clave, "mejorMitad"])
        claveCuentaComb = "-".join([comb, "Z", clave, "count"])
        listaClaves = ['codigo', clavePrmin, clavePrmax, claveProbAbove, claveProbMejorMitad, claveCuentaComb]
        # claveZmean, claveZstd,

        varsCl = dfVars[comb]
        dfR = dfMerc.copy().merge(dfTempEstats).merge(varsCl)
        dfR[clavePrmin] = dfR[claveVmean] + (dfR[claveZmin] * dfR[claveVstd])
        dfR[clavePrmax] = dfR[claveVmean] + (dfR[claveZmax] * dfR[claveVstd])
        dfResult = dfResult.merge(dfR[listaClaves])

    return dfResult


def calculaDFcategACB(dfTemp, dfMerc, clave, filtroFechas=None):
    """ Devuelve un Dataframe con los datos de una cateogría estadística ACB a lo largo de una temporada
    """
    if clave not in dfTemp:
        raise(KeyError, "Clave '%s' no está en datos." % clave)

    if filtroFechas:
        datosWrk = dfTemp
    else:
        datosWrk = dfTemp

    listaCats = ['competicion', 'temporada', 'jornada', 'codigo', clave]
    dfTempEstats = calculaTempStats(datosWrk, clave=clave, filtroFechas=filtroFechas)

    dfResult = dfMerc.copy().merge(
        dfTempEstats).merge(datosWrk[listaCats].set_index(['competicion', 'temporada']).pivot(
            index='codigo', columns='jornada', values=clave).reset_index())

    return dfResult


def calculaDFprecedentes(dfTemp, dfMerc, clave, filtroFechas=None):

    if clave not in dfTemp:
        raise(KeyError, "Clave '%s' no está en datos." % clave)

    if filtroFechas:
        datosWrk = dfTemp
    else:
        datosWrk = dfTemp

    listaCats = ['CODrival', 'rival', 'haGanado', 'jornada', 'Fecha', 'codigo', 'haJugado', 'nombre', 'esLocal', clave]
    #
    dfResult = dfMerc[['codigo', 'CODrival']].merge(datosWrk[listaCats]).merge(calculaTempStats(datosWrk, clave))

    return dfResult

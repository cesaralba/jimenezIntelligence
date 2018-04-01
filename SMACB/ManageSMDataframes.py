'''
Created on Apr 1, 2018

@author: calba
'''

from SMACB.TemporadaACB import calculaTempStats, calculaVars


def calculaDFconVars(dfTemp, dfMerc, clave, filtroFechas=None):
    dfVars = calculaVars(dfTemp, clave=clave, filtroFechas=filtroFechas)
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


# '+/-', 'A', 'BP', 'BR', 'C', 'CODequipo', 'CODrival', 'FP-C', 'FP-F', 'Fecha', 'M', 'P', 'R-D', 'R-O', 'REB-T',
# 'Segs', 'T1%', 'T1-C', 'T1-I', 'T2%', 'T2-C', 'T2-I', 'T3%', 'T3-C', 'T3-I', 'TAP-C', 'TAP-F', 'V', 'Vsm',
# 'codigo', 'competicion', 'dorsal', 'equipo', 'esLocal', 'haGanado', 'haJugado', 'jornada', 'nombre', 'rival',
# 'temporada', 'titular', 'pos']
def calculaDFcatACB(dfTemp, dfMerc, clave, filtroFechas=None):
    dfVars = calculaVars(dfTemp, clave=clave, filtroFechas=filtroFechas)
    dfTempEstats = calculaTempStats(dfTemp, clave=clave, filtroFechas=filtroFechas)

    dfResult = dfMerc.copy().merge(dfTempEstats)

    for comb in dfVars:
        claveZmin = "-".join([comb, clave, "zMin"])
        claveZmax = "-".join([comb, clave, "zMax"])
        claveVmean = "-".join([clave, "mean"])
        claveVstd = "-".join([clave, "std"])
        clavePrmin = "-".join([comb, clave, "predMin"])
        clavePrmax = "-".join([comb, clave, "predMax"])
        #  'RP-V-mejorMitad', 'RP-V-sobreMedia', 'RP-Z-V-mean', 'RP-Z-V-std', 'RP-Z-V-count'
        claveProbAbove = "-".join([comb, clave, "sobreMedia"])
        claveProbMejorMitad = "-".join([comb, clave, "mejorMitad"])
        claveCuentaComb = "-".join([comb, "Z", clave, "count"])
        listaClaves = ['codigo', clavePrmin, clavePrmax, claveProbAbove, claveProbMejorMitad, claveCuentaComb]

        varsCl = dfVars[comb]
        dfR = dfMerc.copy().merge(dfTempEstats).merge(varsCl)
        dfR[clavePrmin] = dfR[claveVmean] + (dfR[claveZmin] * dfR[claveVstd])
        dfR[clavePrmax] = dfR[claveVmean] + (dfR[claveZmax] * dfR[claveVstd])
        dfResult = dfResult.merge(dfR[listaClaves])

    return dfResult

    # dfTemporada[['competicion','temporada','jornada','codigo','V']].set_index(['competicion','temporada'])
    # .pivot(index='codigo',columns='jornada',values='V').columns

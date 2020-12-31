'''
Created on Apr 1, 2018

@author: calba
'''

from SMACB.Constants import POSICIONES
from SMACB.TemporadaACB import calculaTempStats, calculaVars

CATMERCADOFINAL = ['nombre', 'equipo', 'pos', 'cupo', 'Alta', 'lesion', 'info', 'precio', 'prom3Jornadas', 'promVal',
                   'ProxPartido', 'valJornada', 'codigo']
VARSCOLS = ['CODrival', 'esLocal']


def calculaDFconVars(dfTemp, dfMerc, clave, useStd=True, filtroFechas=None):
    dfVars = calculaVars(dfTemp, clave=clave, useStd=useStd, filtroFechas=filtroFechas)
    dfTempEstats = calculaTempStats(dfTemp, clave=clave, filtroFechas=filtroFechas)

    dfResult = dfMerc[CATMERCADOFINAL + VARSCOLS].copy().merge(dfTempEstats)

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

    return dfResult.drop(columns=VARSCOLS).set_index('codigo')


def calculaDFcategACB(dfTemp, dfMerc, clave, filtroFechas=None):
    """ Devuelve un Dataframe con los datos de una cateogría estadística ACB a lo largo de una temporada
    """
    if clave not in dfTemp:
        raise (KeyError, "Clave '%s' no está en datos." % clave)

    if filtroFechas:
        datosWrk = dfTemp
    else:
        datosWrk = dfTemp

    listaCats = ['competicion', 'temporada', 'periodo', 'codigo', clave]
    dfTempEstats = calculaTempStats(datosWrk, clave=clave, filtroFechas=filtroFechas)

    dfAux = datosWrk[listaCats].set_index(['competicion', 'temporada']).pivot(index='codigo', columns='periodo',
                                                                              values=clave).reset_index()

    dfResult = dfMerc[CATMERCADOFINAL].copy().merge(dfTempEstats).merge(dfAux).set_index('codigo')

    return dfResult


COLSPREC = ['Precedente', 'V-prec', 'D-V-prec', 'Z-V-prec', 'Vsm-prec', 'D-Vsm-prec', 'Z-Vsm-prec']


def calculaDFprecedentes(dfTemp, dfMerc, clave, filtroFechas=None):
    if clave not in dfTemp:
        raise (KeyError, "Clave '%s' no está en datos." % clave)

    if filtroFechas:
        datosWrk = dfTemp
    else:
        datosWrk = dfTemp

    datosMrc = dfMerc.copy()
    datosMrc['esLocal'] = datosMrc['proxFuera']

    listaCats = ['CODrival', 'CODequipo', 'equipo', 'rival', 'haGanado', 'jornada', 'Fecha', 'codigo',
                 'haJugado', 'enActa', 'nombre', 'esLocal', clave]

    dfResult = (datosMrc[['codigo', 'CODequipo', 'CODrival', 'esLocal']].merge(datosWrk[listaCats]).merge(
            calculaTempStats(datosWrk, clave)))

    if dfResult.empty:
        return dfResult

    dfResult['Precedente'] = dfResult.apply(datosPartidoPasadoTemp, axis=1)
    dfResult.loc[dfResult['enActa'] & ~dfResult['haJugado'], clave] = 0
    dfResult['D-' + clave + '-prec'] = dfResult[clave] - dfResult[clave + '-mean']
    dfResult['Z-' + clave + '-prec'] = (
            (dfResult[clave] - dfResult[clave + '-mean']) * (1.0 / dfResult[clave + '-std']))

    return (dfResult[['codigo', 'Precedente', clave, 'D-' + clave + '-prec', 'Z-' + clave + '-prec']].rename(
            columns={clave: clave + '-prec'}))


def datosProxPartidoMerc(dfrow):
    result = ("@" if dfrow['proxFuera'] else "vs ") + dfrow['rival']
    return result


def datosPartidoPasadoTemp(dfrow):
    if dfrow['enActa']:
        rival = ("vs " if dfrow['esLocal'] else "@") + dfrow['rival']
        resultPartido = "(V)" if dfrow['haGanado'] else "(D)"
        if str(dfrow['Fecha']) != "NaT":
            jornada = dfrow['jornada']
            fecha = dfrow['Fecha']
            resultPartido = "(V)" if dfrow['haGanado'] else "(D)"
            jugo = "" if dfrow['haJugado'] else ": No jugo"
            result = "%s %s (%i:%s)%s" % (rival, resultPartido, jornada, fecha, jugo)
        else:
            result = "-"

    else:
        result = "-"

    return result


def datosPosMerc(dfrow):
    return POSICIONES.get(dfrow['pos'], dfrow['pos'])


def datosLesionMerc(dfrow):
    resL = "Si" if dfrow['lesion'] else "No"
    resInfo = (": %s" % dfrow['info']) if dfrow['info'] else ""

    return "%s%s" % (resL, resInfo)

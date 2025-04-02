from _operator import itemgetter
from collections import namedtuple
from copy import copy

import pandas as pd

import SMACB.Programa.Globals
from SMACB.Constants import infoSigPartido, LocalVisitante, DEFAULTNUMFORMAT, TRADPOSICION
from SMACB.TemporadaACB import TemporadaACB, esEstCreciente, auxEtiqPartido
from .Constantes import ESTADISTICOEQ, REPORTLEYENDAS, ESTADISTICOJUG, COLS_IDENTIFIC_JUG
from .FuncionesAux import auxCalculaBalanceStrSuf, GENERADORETTIRO, GENERADORETREBOTE
from .Globals import recuperaEstadsGlobales, recuperaClasifLiga

sentinel = object()

estadGlobalesOrdenX = SMACB.Programa.Globals.estadGlobalesOrden

filaComparEstadistica = namedtuple('filaComparEstadistica',
                                   ['magn', 'isAscending', 'locAbr', 'locMagn', 'locRank', 'locHigh', 'maxMagn',
                                    'maxAbr', 'maxHigh', 'ligaMed', 'ligaStd', 'minMagn', 'minAbr', 'minHigh', 'visAbr',
                                    'visMagn', 'visRank', 'visHigh', 'nombreMagn', 'formatoMagn', 'leyenda'])
tuplaMaxMinMagn = namedtuple('tuplaMaxMinMagn',
                             ['minVal', 'minEtq', 'minAbrevs', 'maxVal', 'maxEtq', 'maxAbrevs', 'abrevs2add'])


def auxFindTargetAbrevs(tempData: TemporadaACB, datosSig: infoSigPartido, ):
    sigPartido = datosSig.sigPartido
    result = {k: list(tempData.Calendario.abrevsEquipo(sigPartido['loc2abrev'][k]).intersection(
        SMACB.Programa.Globals.estadGlobales.index))[0] for k in LocalVisitante}

    return result


def calculaMaxMinMagn(ser: pd.Series, ser_orden: pd.Series):
    def getValYEtq(serie, serie_orden, targ_orden):
        auxSerTargOrden: pd.Series = serie_orden == targ_orden
        numOrdenTarg = auxSerTargOrden.sum()
        abrevs = set(auxSerTargOrden[auxSerTargOrden].index)
        etiqTarg = f"x{numOrdenTarg}" if numOrdenTarg > 1 else serie_orden[serie_orden == targ_orden].index[0]
        valTarg = serie[serie_orden == targ_orden].iloc[0]
        return valTarg, etiqTarg, abrevs

    # Mejor cuanto el orden sea menor: 1 mejor > 18 peor
    maxVal, maxEtq, maxAbrevs = getValYEtq(ser, ser_orden, ser_orden.min())
    minVal, minEtq, minAbrevs = getValYEtq(ser, ser_orden, ser_orden.max())

    return tuplaMaxMinMagn(minVal=minVal, minEtq=minEtq, minAbrevs=minAbrevs, maxVal=maxVal, maxEtq=maxEtq,
                           maxAbrevs=maxAbrevs, abrevs2add=maxAbrevs.union(minAbrevs))


def datosAnalisisEstadisticos(tempData: TemporadaACB, datosSig: infoSigPartido, magn2include: list, magnsAscending=None,
                              infoCampos: dict = sentinel
                              ):
    if infoCampos is sentinel:
        infoCampos = REPORTLEYENDAS

    catsAscending = magnsAscending if magnsAscending else set()
    auxEtiqLeyenda = infoCampos if infoCampos else {}

    recuperaEstadsGlobales(tempData)

    targetAbrevs = auxFindTargetAbrevs(tempData, datosSig)

    result = {}

    estadsInexistentes = set()
    abrevs2leyenda = set()
    clavesEnEstads = set(sorted(SMACB.Programa.Globals.estadGlobales.columns))

    for claveEst in magn2include:

        kEq, kMagn = claveEst

        if kMagn not in auxEtiqLeyenda:
            print(f"tablaAnalisisEstadisticos.filasTabla: magnitud '{kMagn}' no está en descripciones.Usando {kMagn} "
                  f"para etiqueta")
        descrMagn = auxEtiqLeyenda.get(kMagn, {})

        etiq = descrMagn.get('etiq', kMagn)
        formatoMagn = descrMagn.get('formato', DEFAULTNUMFORMAT)
        leyendaMagn = descrMagn.get('leyenda', None)

        clave2use = (kEq, kMagn, ESTADISTICOEQ)
        if clave2use not in clavesEnEstads:
            estadsInexistentes.add(clave2use)
            continue

        esCreciente = esEstCreciente(kMagn, catsAscending, kEq)
        labCreciente = "C" if esCreciente else "D"

        serMagn: pd.Series = SMACB.Programa.Globals.estadGlobales[clave2use]
        serMagnOrden: pd.Series = SMACB.Programa.Globals.estadGlobalesOrden[clave2use]
        magnMed = serMagn.mean()
        magnStd = serMagn.std()

        datosEqs = {k: serMagn[targetAbrevs[k]] for k in LocalVisitante}
        datosEqsOrd = {k: int(serMagnOrden[targetAbrevs[k]]) for k in LocalVisitante}

        infoMaxMinMagn = calculaMaxMinMagn(serMagn, serMagnOrden)
        abrevs2leyenda = abrevs2leyenda.union(infoMaxMinMagn.abrevs2add)

        resaltaLocal = datosEqsOrd['Local'] < datosEqsOrd['Visitante']
        resaltaVisit = datosEqsOrd['Visitante'] < datosEqsOrd['Local']

        resaltaMax = min(serMagnOrden) in set(datosEqsOrd.values())
        resaltaMin = max(serMagnOrden) in set(datosEqsOrd.values())

        newRecord = filaComparEstadistica(magn=kMagn, nombreMagn=etiq, isAscending=labCreciente,
                                          locAbr=targetAbrevs['Local'], locMagn=datosEqs['Local'], locHigh=resaltaLocal,
                                          locRank=datosEqsOrd['Local'], maxMagn=infoMaxMinMagn.maxVal,
                                          maxAbr=infoMaxMinMagn.maxEtq, maxHigh=resaltaMax, ligaMed=magnMed,
                                          ligaStd=magnStd, minMagn=infoMaxMinMagn.minVal, minAbr=infoMaxMinMagn.minEtq,
                                          minHigh=resaltaMin, visAbr=targetAbrevs['Visitante'],
                                          visMagn=datosEqs['Visitante'], visRank=datosEqsOrd['Visitante'],
                                          visHigh=resaltaVisit, formatoMagn=formatoMagn, leyenda=leyendaMagn)

        result[claveEst] = newRecord

    if estadsInexistentes:
        raise ValueError(
            f"datosAnalisisEstadisticos: los siguientes valores no existen: {estadsInexistentes}. Parametro: "
            f"{magn2include}. Columnas posibles: {clavesEnEstads}")
    return result, abrevs2leyenda


def datosRestoJornada(tempData: TemporadaACB, datosSig: infoSigPartido):
    """
    Devuelve la lista de partidos de la jornada a la que corresponde  el partidos siguiente del equipo objetivo
    :param tempData: datos descargados de ACB (ya cargados, no el fichero)
    :param datosSig: resultado de tempData.sigPartido (info sobre el siguiente partido del equipo objetivo
    :return: lista con información sobre partidos sacada del Calendario
    """
    result = []
    sigPartido = datosSig.sigPartido
    jornada = int(sigPartido['jornada'])
    calJornada = tempData.Calendario.Jornadas[jornada]

    for p in calJornada['partidos']:
        urlPart = p['url']
        part = tempData.Partidos[urlPart]
        data = copy(p)
        data['fechaPartido'] = part.fechaPartido
        result.append(data)

    result.extend([p for p in calJornada['pendientes'] if p['participantes'] != sigPartido['participantes']])
    result.sort(key=itemgetter('fechaPartido'))

    return result


def datosJugadores(tempData: TemporadaACB, abrEq, partJug):
    COLS_TRAYECT_TEMP_orig_names = ['enActa', 'haJugado', 'esTitular', 'haGanado', ]
    COLS_TRAYECT_TEMP_orig = [(col, 'sum') for col in COLS_TRAYECT_TEMP_orig_names]
    COLS_TRAYECT_TEMP = ['Acta', 'Jugados', 'Titular', 'Vict']
    COLS_FICHA = ['id', 'alias', 'pos', 'altura', 'licencia', 'fechaNac', 'Activo']
    VALS_ESTAD_JUGADOR = ['A', 'A-BP', 'A-TCI', 'BP', 'BR', 'FP-C', 'FP-F', 'P', 'ppTC', 'R-D', 'R-O', 'REB-T', 'Segs',
                          'T1-C', 'T1-I', 'T1%', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-I', 'TC-C', 'TC%',
                          'PTC', 'TAP-C', 'TAP-F']

    COLS_ESTAD_PROM = [(col, ESTADISTICOJUG) for col in VALS_ESTAD_JUGADOR]
    COLS_ESTAD_TOTAL = [(col, 'sum') for col in VALS_ESTAD_JUGADOR]

    abrevsEq = tempData.Calendario.abrevsEquipo(abrEq)

    auxDF = tempData.extraeDataframeJugadores(listaURLPartidos=partJug)

    jugDF = auxDF.loc[auxDF['CODequipo'].isin(abrevsEq)]

    estadsJugDF = tempData.dfEstadsJugadores(jugDF, abrEq=abrEq)
    fichasJugadores = tempData.dataFrameFichasJugadores(abrEq=abrEq)
    fichasJugadores.posicion = fichasJugadores.posicion.map(TRADPOSICION)

    COLS_IDENTIFIC_JUG_aux = COLS_IDENTIFIC_JUG.copy()
    COLS_FICHA_aux = COLS_FICHA.copy()

    if 'dorsal' in fichasJugadores.columns:
        COLS_IDENTIFIC_JUG_aux.remove('dorsal')
        COLS_FICHA_aux.append('dorsal')

    trayectTemp = estadsJugDF[COLS_TRAYECT_TEMP_orig]
    trayectTemp.columns = pd.Index(COLS_TRAYECT_TEMP)

    identifJug = pd.concat([estadsJugDF['Jugador'][COLS_IDENTIFIC_JUG_aux], fichasJugadores[COLS_FICHA_aux]], axis=1,
                           join="inner")

    estadsPromedios = estadsJugDF[COLS_ESTAD_PROM].droplevel(1, axis=1)
    estadsTotales = estadsJugDF[COLS_ESTAD_TOTAL].droplevel(1, axis=1)
    datosUltPart = jugDF.sort_values('fechaPartido').groupby('codigo').tail(n=1).set_index('codigo', drop=False)
    datosUltPart['Partido'] = datosUltPart.apply(
        lambda p: auxEtiqPartido(tempData, p['CODrival'], esLocal=p['esLocal']), axis=1)

    dataFramesAJuntar = {'Jugador': identifJug, 'Trayectoria': trayectTemp, 'Promedios': estadsPromedios,
                         # .drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP)
                         'Totales': estadsTotales,  # .drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP)
                         'UltimoPart': datosUltPart}  # .drop(columns=COLS_IDENTIFIC_JUG)
    result = pd.concat(dataFramesAJuntar.values(), axis=1, join='outer', keys=dataFramesAJuntar.keys())

    return result


filaTablaClasif = namedtuple('filaTablaClasif',
                             ['posic', 'nombre', 'jugs', 'victs', 'derrs', 'ratio', 'puntF', 'puntC', 'diffP',
                              'resalta'])


def datosTablaClasif(tempData: TemporadaACB, datosSig: infoSigPartido) -> list[filaTablaClasif]:
    # Data preparation
    sigPartido = datosSig.sigPartido
    abrsEqs = sigPartido['participantes']
    jornada = int(sigPartido['jornada'])
    muestraJornada = len(tempData.Calendario.Jornadas[jornada]['partidos']) > 0

    recuperaClasifLiga(tempData)

    result = []
    for posic, eq in enumerate(SMACB.Programa.Globals.clasifLiga):
        nombEqAux = eq.nombreCorto
        notaClas = auxCalculaBalanceStrSuf(record=eq, addPendientes=True, currJornada=jornada,
                                           addPendJornada=muestraJornada,
                                           jornadasCompletas=tempData.jornadasCompletas())
        nombEq = f"{nombEqAux}{notaClas}"
        victs = eq.V
        derrs = eq.D
        jugs = victs + derrs
        ratio = (100.0 * victs / jugs) if (jugs != 0) else 0.0
        puntF = eq.Pfav
        puntC = eq.Pcon
        diffP = puntF - puntC
        resaltaFila = bool(abrsEqs.intersection(eq.abrevsEq))

        fila = filaTablaClasif(posic=posic + 1, nombre=nombEq, jugs=jugs, victs=victs, derrs=derrs, ratio=ratio,
                               puntF=puntF, puntC=puntC, diffP=diffP, resalta=resaltaFila)

        result.append(fila)

    return result


INFOESTADSEQ = {('Eq', 'P'): {'etiq': 'PF', 'formato': 'float'}, ('Rival', 'P'): {'etiq': 'PC', 'formato': 'float'},
                ('Eq', 'POS'): {'etiq': 'Pos', 'formato': 'float'}, ('Eq', 'OER'): {'etiq': 'OER', 'formato': 'float'},
                ('Rival', 'OER'): {'etiq': 'DER', 'formato': 'float'},
                ('Eq', 'T2'): {'etiq': 'T2', 'generador': GENERADORETTIRO(tiro='2', entero=False, orden=True)},
                ('Eq', 'T3'): {'etiq': 'T3', 'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Eq', 'TC'): {'etiq': 'TC', 'generador': GENERADORETTIRO(tiro='C', entero=False, orden=True)},
                ('Eq', 'ppTC'): {'etiq': 'P / TC-I', 'formato': 'float'},
                ('Eq', 'PTC/PTCPot'): {'etiq': '%PPot', 'formato': 'float'},
                ('Eq', 't3/tc-I'): {'etiq': 'T3-I / TC-I', 'formato': 'float'},
                ('Eq', 'FP-F'): {'etiq': 'F com', 'formato': 'float'},
                ('Eq', 'FP-C'): {'etiq': 'F rec', 'formato': 'float'},
                ('Eq', 'T1'): {'etiq': 'T1', 'generador': GENERADORETTIRO(tiro='1', entero=False, orden=True)},
                ('Eq', 'REB'): {'etiq': 'Rebs', 'ancho': 17, 'generador': GENERADORETREBOTE(entero=False, orden=True)},
                ('Eq', 'EffRebD'): {'etiq': 'F rec', 'formato': 'float'},
                ('Eq', 'EffRebO'): {'etiq': 'F rec', 'formato': 'float'}, ('Eq', 'A'): {'formato': 'float'},
                ('Eq', 'BP'): {'formato': 'float'}, ('Eq', 'BR'): {'formato': 'float'},
                ('Eq', 'A/BP'): {'formato': 'float'}, ('Eq', 'A/TC-C'): {'etiq': 'A/Can', 'formato': 'float'},
                ('Eq', 'PNR'): {'formato': 'float'},

                ('Rival', 'T2'): {'generador': GENERADORETTIRO(tiro='2', entero=False, orden=True)},
                ('Rival', 'T3'): {'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'TC'): {'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'ppTC'): {'etiq': 'P / TC-I', 'formato': 'float'},
                ('Rival', 'PTC/PTCPot'): {'etiq': '%PPot', 'formato': 'float'},
                ('Rival', 't3/tc-I'): {'etiq': 'T3-I / TC-I', 'formato': 'float'},
                ('Rival', 'T1'): {'etiq': 'TL', 'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'REB'): {'etiq': 'Rebs', 'ancho': 17,
                                   'generador': GENERADORETREBOTE(entero=False, orden=True)},
                ('Rival', 'A'): {'formato': 'float'}, ('Rival', 'BP'): {'formato': 'float'},
                ('Rival', 'BR'): {'formato': 'float'}, ('Rival', 'A/BP'): {'formato': 'float'},
                ('Rival', 'A/TC-C'): {'etiq': 'A/Can', 'formato': 'float'}, ('Rival', 'PNR'): {'formato': 'float'}, }

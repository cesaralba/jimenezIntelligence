from collections import namedtuple, defaultdict
from copy import copy
from operator import itemgetter
from typing import Optional

import pandas as pd

import SMACB.Programa.Globals as GlobACB
from SMACB.Constants import infoSigPartido, LocalVisitante, DEFAULTNUMFORMAT, TRADPOSICION, OtherLoc, infoJornada
from SMACB.Programa.Clasif import entradaClas2kEmpatePareja, infoGanadorEmparej, \
    infoClasifComplPareja, calculaClasifEquipoLR
from SMACB.Programa.Constantes import ESTADISTICOEQ, REPORTLEYENDAS, ESTADISTICOJUG, COLS_IDENTIFIC_JUG
from SMACB.Programa.FuncionesAux import auxCalculaBalanceStrSuf, GENERADORETTIRO, GENERADORETREBOTE, \
    etiquetasClasificacion, auxCalculaFirstBalNeg, FMTECHACORTA, auxEtiqPartido, esEstCreciente
from SMACB.Programa.Globals import recuperaEstadsGlobales, recuperaClasifLigaLR, clasifLiga2dict
from SMACB.TemporadaACB import TemporadaACB

sentinel = object()

filaComparEstadistica = namedtuple('filaComparEstadistica',
                                   ['magn', 'isAscending', 'locAbr', 'locMagn', 'locRank', 'locHigh', 'maxMagn',
                                    'maxAbr', 'maxHigh', 'ligaMed', 'ligaStd', 'minMagn', 'minAbr', 'minHigh', 'visAbr',
                                    'visMagn', 'visRank', 'visHigh', 'nombreMagn', 'formatoMagn', 'leyenda'])
tuplaMaxMinMagn = namedtuple('tuplaMaxMinMagn',
                             ['minVal', 'minEtq', 'minAbrevs', 'maxVal', 'maxEtq', 'maxAbrevs', 'abrevs2add'])

filaTablaClasif = namedtuple('filaTablaClasif',
                             ['posic', 'nombre', 'jugs', 'victs', 'derrs', 'ratio', 'puntF', 'puntC', 'diffP',
                              'resalta'])


def auxFindTargetAbrevs(tempData: TemporadaACB, datosSig: infoSigPartido, ):
    sigPartido = datosSig.sigPartido
    result = {
        k: list(tempData.Calendario.abrevsEquipo(sigPartido['loc2abrev'][k]).intersection(GlobACB.estadGlobales.index))[
            0] for k in LocalVisitante}

    return result


def calculaMaxMinMagn(ser: pd.Series, ser_orden: pd.Series):
    def getValYEtq(serie, serie_orden, targ_orden):
        auxSerTargOrden: pd.Series = serie_orden == targ_orden
        numOrdenTarg = auxSerTargOrden.sum()
        abrevs = set(auxSerTargOrden[auxSerTargOrden].index)
        etiqTarg = f"x{numOrdenTarg}" if numOrdenTarg > 1 else serie_orden[serie_orden == targ_orden].index[0]
        valTarg = serie[serie_orden == targ_orden].iloc[0]
        return valTarg, etiqTarg, abrevs

    auxSer = ser.rename(axis=0, index=GlobACB.tradEquipos['i2a'], inplace=False)
    auxSerOrden = ser_orden.rename(axis=0, index=GlobACB.tradEquipos['i2a'], inplace=False)
    # Mejor cuanto el orden sea menor: 1 mejor > 18 peor
    maxVal, maxEtq, maxAbrevs = getValYEtq(auxSer, auxSerOrden, auxSerOrden.min())
    minVal, minEtq, minAbrevs = getValYEtq(auxSer, auxSerOrden, auxSerOrden.max())

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
    targetAbrevs = dict(zip(LocalVisitante, datosSig.abrevLV))
    targetIds = dict(zip(LocalVisitante, datosSig.idLV))

    result = {}

    estadsInexistentes = set()
    abrevs2leyenda = set()
    clavesEnEstads = set(GlobACB.estadGlobales.columns)

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

        serMagn: pd.Series = GlobACB.estadGlobales[clave2use]
        serMagnOrden: pd.Series = GlobACB.estadGlobalesOrden[clave2use]
        serMagn.rename(index=GlobACB.tradEquipos['i2a'])
        serMagnOrden.rename(index=GlobACB.tradEquipos['i2a'])

        magnMed = serMagn.mean()
        magnStd = serMagn.std()
        datosEqs = {k: serMagn[targetIds[k]] for k in LocalVisitante}
        datosEqsOrd = {k: int(serMagnOrden[targetIds[k]]) for k in LocalVisitante}

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
    jornada = sigPartido['jornada']
    calJornada = tempData.Calendario.Jornadas[jornada]
    urlPart2K = tempData.idPartsDescargados()[1]

    for p in calJornada['partidos']:
        urlPart = p['url']
        part = tempData.Partidos[urlPart2K[urlPart]]
        data = copy(p)
        data['fechaPartido'] = part.fechaPartido
        result.append(data)

    result.extend([p for p in calJornada['pendientes'] if p['participantes'] != sigPartido['participantes']])
    result.sort(key=itemgetter('fechaPartido'))

    return result


COLS_TRAYECT_TEMP_orig = [(col, 'sum') for col in ['enActa', 'haJugado', 'esTitular', 'haGanado', ]]
COLS_TRAYECT_TEMP = ['Acta', 'Jugados', 'Titular', 'Vict']
COLS_FICHA = ['id', 'alias', 'pos', 'altura', 'licencia', 'fechaNac', 'Activo']
VALS_ESTAD_JUGADOR = ['A', 'A/BP', 'A/TC-I', 'BP', 'BR', 'FP-C', 'FP-F', 'P', 'ppTC', 'R-D', 'R-O', 'REB-T', 'Segs',
                      'T1-C', 'T1-I', 'T1%', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-I', 'TC-C', 'TC%',
                      'PTC', 'TAP-C', 'TAP-F']

COLS_ESTAD_PROM = [(col, ESTADISTICOJUG) for col in VALS_ESTAD_JUGADOR]
COLS_ESTAD_TOTAL = [(col, 'sum') for col in VALS_ESTAD_JUGADOR]


def datosJugadores(tempData: TemporadaACB, abrEq, partJug):
    abrevsEq = tempData.Calendario.abrevsEquipo(abrEq)

    auxDF = tempData.extraeDataframeJugadores(listaClavePartidos=partJug)

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
                         'Totales': estadsTotales, 'UltimoPart': datosUltPart}
    result = pd.concat(dataFramesAJuntar.values(), axis=1, join='outer', keys=dataFramesAJuntar.keys())

    return result


def datosTotalEquipo(tempData: TemporadaACB, abrEq: str) -> pd.DataFrame:
    # TODO: T2026 incluir la fila de entrenadores aqui?
    partsEq: pd.Series = tempData.dfEstadsEquipo(
        tempData.dfPartidosLV2ER(tempData.dataFramePartidosLV(abrEq), abrEq=abrEq), abrEq=abrEq)
    auxDF = pd.DataFrame(partsEq).T

    colsDeInteres = [c for c in auxDF.columns if c[0] == 'Eq']
    colsRenomb = [(c1, c2) for c0, c1, c2 in auxDF.columns if c0 == 'Eq']
    datosParts = auxDF[colsDeInteres]
    datosParts.columns = colsRenomb

    datosIdent = pd.DataFrame([["TOTAL", 'Total', 'Dorsal']], columns=pd.Index(data=['nombre', 'Activo', '999']))

    datosTrayect = auxDF[[('Eq', 'Vict', 'count'), ('Eq', 'Vict', 'sum')]]
    datosTrayect.columns = pd.Index(data=['Jugados', 'Vict'])

    estadsPromedios = datosParts[COLS_ESTAD_PROM]
    estadsPromedios.columns = pd.Index([c0 for c0, _ in estadsPromedios.columns])
    estadsTotales = datosParts[COLS_ESTAD_TOTAL]
    estadsTotales.columns = pd.Index([c0 for c0, _ in estadsTotales.columns])

    dataFramesAJuntar = {'Jugador': datosIdent, 'Trayectoria': datosTrayect, 'Promedios': estadsPromedios,
                         'Totales': estadsTotales}
    result: pd.DataFrame = pd.concat(dataFramesAJuntar.values(), axis=1, join='outer', keys=dataFramesAJuntar.keys())

    result.index = pd.Index(["999999999999"])

    return result


def datosTablaClasif(tempData: TemporadaACB, datosSig: infoSigPartido) -> list[filaTablaClasif]:
    # Data preparation
    datosJornada: infoJornada = datosSig.sigPartido['infoJornada']
    abrsEqs = datosSig.sigPartido['participantes']

    jornada = datosJornada.jornada
    muestraJornada = len(tempData.Calendario.Jornadas[jornada]['partidos']) > 0

    recuperaClasifLigaLR(tempData)

    result = []
    for posic, eq in enumerate(GlobACB.clasifLigaLR):
        notaClas = ""
        if not datosJornada.esPlayOff:
            notaClas = auxCalculaBalanceStrSuf(record=eq, addPendientes=True, currJornada=jornada,
                                               addPendJornada=muestraJornada,
                                               jornadasCompletas=tempData.jornadasCompletas())
        nombEq = f"{eq.nombreCorto}{notaClas}"
        jugs = eq.V + eq.D
        ratio = (100.0 * eq.V / jugs) if (jugs != 0) else 0.0
        resaltaFila = bool(abrsEqs.intersection(eq.abrevsEq))

        fila = filaTablaClasif(posic=posic + 1, nombre=nombEq, jugs=jugs, victs=eq.V, derrs=eq.D, ratio=ratio,
                               puntF=eq.Pfav, puntC=eq.Pcon, diffP=(eq.Pfav - eq.Pcon), resalta=resaltaFila)

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


def extraeDatosCruces(tempData: TemporadaACB):
    recuperaClasifLigaLR(tempData=tempData)
    datosLR = clasifLiga2dict(tempData=tempData)

    acumulador = defaultdict(lambda: {'pendientes': 2})

    for p in tempData.Partidos.values():
        if tempData.Calendario.Jornadas[p.jornada]['esPlayoff']:
            continue

        clave = tuple(sorted([str(p.EquiposCalendario[loc]['id']) for loc in LocalVisitante]))
        acumulador[clave]['pendientes'] -= 1

        datosPart = p.DatosSuministrados['equipos']
        for loc in LocalVisitante:
            datos = datosPart[loc]
            datosOtro = datosPart[OtherLoc(loc)]
            idEq = datos['id']
            diffP = datos['puntos'] - datosOtro['puntos']
            if datos['haGanado']:
                sufLoc = "L" if loc == "Local" else "V"
                acumulador[clave]['prec'] = (idEq, sufLoc, diffP)

        if acumulador[clave]['pendientes'] == 0:
            acumulador[clave].pop('prec')

            auxGameList = tempData.extractGameList(idEquipos=set(clave), playOffStatus=False)
            l1 = [calculaClasifEquipoLR(dataTemp=tempData, idEq=eq, gameList=auxGameList) for eq in clave]

            sortkeys = sorted([(infoClas.idEq, entradaClas2kEmpatePareja(infoClas, datosLR)) for infoClas in l1],
                              key=itemgetter(1), reverse=True)
            acumulador[clave]['ganador'] = infoGanadorEmparej(sortkeys)

    return acumulador


def preparaInfoCruces(tempData: TemporadaACB):
    GlobACB.recuperaClasifLigaLR(tempData)

    result = {}

    result['equipos'] = etiquetasClasificacion(GlobACB.clasifLigaLR)
    result['firstNegBal'] = auxCalculaFirstBalNeg(GlobACB.clasifLigaLR)
    result['datosDiagonal'] = preparaDatosDiagonalYMargenes(tempData=tempData)
    result['datosContadores'] = defaultdict(
        lambda: {'G': 0, 'P': 0, 'Pdte': 0, 'PendV': 0, 'PendD': 0, 'crit': defaultdict(int)})
    result['datosTotales'] = {'Resueltos': 0, 'Pdtes': 0,
                              'criterios': {'res': defaultdict(int), 'pend': defaultdict(int)}}

    infoCruce = namedtuple('infoCruce', field_names=['eq1', 'eq2', 'info'])

    result['resueltos'] = []
    result['pendientes'] = []

    datosCruces = extraeDatosCruces(tempData)

    for clave, estado in datosCruces.items():
        if 'prec' in estado:
            result['datosTotales']['Pdtes'] += 1
            abrGan, locGan, _ = estado['prec']
            result['datosTotales']['criterios']['pend'][locGan] += 1
            result['pendientes'].append(infoCruce(eq1=clave[0], eq2=clave[1], info=estado['prec']))
            for idEq in clave:
                result['datosContadores'][idEq]['Pdte'] += 1
                result['datosContadores'][idEq]['PendV' if (idEq == abrGan) else 'PendD'] += 1
        elif 'ganador' in estado:
            result['datosTotales']['Resueltos'] += 1
            abrGan, critGan, _ = estado['ganador']
            result['datosTotales']['criterios']['res'][critGan] += 1
            result['resueltos'].append(infoCruce(eq1=clave[0], eq2=clave[1], info=estado['ganador']))
            for idEq in clave:
                result['datosContadores'][idEq]['G' if (idEq == abrGan) else 'P'] += 1
                if idEq == abrGan:
                    result['datosContadores'][idEq]['crit'][critGan] += 1
        else:
            raise ValueError(f"No se tratar Cruce: {clave}:{estado}")

    result['clavesAmostrar'] = [crit for crit in infoClasifComplPareja._fields if
                                crit in result['datosTotales']['criterios']['res']]

    return result


def preparaDatosDiagonalYMargenes(tempData: TemporadaACB, currJornada: Optional[int] = None, jornadasCompletas=None):
    muestraJornada = (
            len(tempData.Calendario.Jornadas[currJornada]['partidos']) > 0) if currJornada is not None else False

    result = {}

    for pos, eq in enumerate(GlobACB.clasifLigaLR, start=1):
        auxResult = {'pos': pos, 'diffP': (eq.Pfav - eq.Pcon), 'balanceTotal': f"{eq.V}-{eq.D}",
                     'balanceLocal': f"{eq.CasaFuera['Local'].V}-{eq.CasaFuera['Local'].D}",
                     'balanceVisitante': f"{eq.CasaFuera['Visitante'].V}-{eq.CasaFuera['Visitante'].D}",
                     'abrev': eq.abrevAusar, 'idEq': eq.idEq}

        if (currJornada is not None) and (jornadasCompletas is not None):
            auxResult['sufParts'] = auxCalculaBalanceStrSuf(eq, addPendientes=True, currJornada=currJornada,
                                                            addPendJornada=muestraJornada,
                                                            jornadasCompletas=jornadasCompletas)

        result[eq.idEq] = auxResult

    return result


infoEquipoPartido = namedtuple('infoEquipoPartido', field_names=['loc', 'abrev', 'idEq', 'puntos', 'haGanado'],
                               defaults=[None, None])
infoPartido = namedtuple('infoPartido', field_names=['jornada', 'fechaPartido', 'pendiente', 'Local', 'Visitante'])


def auxEquipoCalendario2InfoEqPartido(data, loc) -> infoEquipoPartido:
    auxResult = {'loc': loc}
    for k in ['abrev', 'puntos', 'haGanado']:
        auxResult[k] = data.get(k, None)
    # TODO: 26-27 asegurarse que sólo haya idEq
    auxResult['idEq'] = data.get('idEq', data.get('id', None))
    return infoEquipoPartido(**auxResult)


def auxEquipoCalendario2InfoPartido(data) -> infoPartido:
    auxResult = {}
    for k in ['jornada', 'fechaPartido', 'pendiente']:
        auxResult[k] = data[k]
    for k in LocalVisitante:
        auxResult[k] = auxEquipoCalendario2InfoEqPartido(data['equipos'][k], k)
    return infoPartido(**auxResult)


def extraeInfoTablaLiga(tempData: TemporadaACB):
    resultado = {'jugados': [], 'pendientes': [], 'totales': {'Victoria': {loc: 0 for loc in LocalVisitante}}}

    for data in tempData.Calendario.Jornadas.values():
        if data['esPlayoff']:
            continue

        for part in data['partidos']:
            infoPart = auxEquipoCalendario2InfoPartido(part)
            resultado['jugados'].append(infoPart)
            resultado['totales']['Victoria']['Local' if infoPart.Local.haGanado else 'Visitante'] += 1

        for part in data['pendientes']:
            resultado['pendientes'].append(auxEquipoCalendario2InfoPartido(part))
    return resultado


def preparaInfoLigaReg(tempData: TemporadaACB, currJornada: int = None):
    GlobACB.recuperaClasifLigaLR(tempData)
    jornadasCompletas = tempData.jornadasCompletas()

    result = {'jugados': [], 'pendientes': []}

    result['equipos'] = etiquetasClasificacion(GlobACB.clasifLigaLR)
    result['firstNegBal'] = auxCalculaFirstBalNeg(GlobACB.clasifLigaLR)
    result['datosDiagonal'] = preparaDatosDiagonalYMargenes(tempData=tempData, currJornada=currJornada,
                                                            jornadasCompletas=jornadasCompletas)

    datosLiga = extraeInfoTablaLiga(tempData=tempData)
    result['totales'] = datosLiga['totales']

    for pJug in datosLiga['jugados']:
        resultadoStr = f"{pJug.Local.puntos}-{pJug.Visitante.puntos}"
        auxResult = (pJug.Local.idEq, pJug.Visitante.idEq, pJug.jornada, resultadoStr, pJug.Local.abrev,
                     pJug.Visitante.abrev)
        result['jugados'].append(auxResult)
    for pPend in datosLiga['pendientes']:
        fechaStr = 'TBD' if (pPend.fechaPartido is None) else pPend.fechaPartido.strftime(FMTECHACORTA)
        auxResult = (pPend.Local.idEq, pPend.Visitante.idEq, pPend.jornada, fechaStr, pPend.Local.abrev,
                     pPend.Visitante.abrev)
        result['pendientes'].append(auxResult)

    return result

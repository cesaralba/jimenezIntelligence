import logging
from typing import Dict, Optional, List, Tuple

import pandas as pd

from SMACB.Constants import LocalVisitante, OtherLoc, numPartidoPO2jornada, infoJornada
from Utils.Misc import copyDictWithTranslation, createDictOfType
from Utils.ParseoData import ProcesaTiempo

LV2HA = {'Local': 'home', 'Visitante': 'away'}
HA2LV = {'home': 'Local', 'away': 'Visitante'}
IsH2LOC = dict(zip([True, False], LocalVisitante))

jugadaTag2Desc = {
    (92, None): "T1-C",
    (93, None): "T2-C",
    (94, None): "T3-C",
    (96, None): "T1-F",
    (97, None): "T2-F",
    (98, None): "T3-F",

    (100, None): "Mate",
    (101, None): "Rebote of",
    (102, None): "Tapón",
    (103, None): "Recuperación",
    (104, None): "Rebote def",
    (105, None): "Tapón rec",

    (106, None): "Pérdida",
    (106, 1): "Pérdida - pasos",
    (106, 2): 'Pérdida - 3" zona',
    (106, 7): "Pérdida - final pos",
    (106, 8): 'Pérdida - infracción 8"',
    (106, 11): "Pérdida - balón retenido",
    (106, 12): "Pérdida - mal pase",
    (106, 13): "Pérdida - balón perdido",
    (106, 14): "Pérdida - dobles",
    (106, 15): "Pérdida - campo atrás",

    (107, None): "Asistencia (2p)",
    (108, None): "Asistencia (3p)",
    (109, None): "Falta ataque",
    (110, None): "Falta rec",
    (112, None): "Cambio - Entra",
    (113, None): "Tiempo muerto",
    (115, None): "Cambio - Sale",

    (116, None): "Final periodo",
    (118, None): "Tiempo muerto TV",
    (119, None): "Asistencia (FP)",
    (121, None): "Gana posesión?",
    (123, None): "Final partido",
    (159, None): "Falta pers 0TL",

    (160, None): "Falta pers 1TL",
    (161, None): "Falta pers 2TL",
    (162, None): "Falta pers 3TL",
    (166, None): "Falta antideportiva",
    (168, None): "Falta antideportiva compensada",
    (173, None): "Falta técnica compensada",
    (178, None): "Salto ganado",
    (179, None): "Salto perdido",

    (406, None): "Rev - Tipo de tiro",
    (407, None): "Rev - Canasta válida",
    (409, None): "Rev - Reloj de partido",
    (410, None): "Rev - Enfrentamiento",
    (411, None): "Rev - Tipo de falta",
    (413, None): "Rev - Ult jug tocar",
    (415, None): "Rev - Cambios",
    (416, None): "Challenge Ent loc",
    (417, None): "Challenge Ent vis",
    (533, None): "Mate fallado",
    (537, None): "Falta técnica 1TL",
    (540, None): "Técnica entrenador",
    (599, None): "Entra a pista (quint inicial)",
    (748, None): "Challenge ganado",
    (749, None): "Challenge perdido",
}


def procesaMDcalFl2calendarIDs(rawData: dict) -> Dict[str, Dict]:
    result = {'compKey2compId': {}, 'compId2compKey': {}, 'seaId2seaYear': {}, 'seaYear2seaId': {}, 'seaData': {},
              'currFilters': {}}

    auxFilterData: dict = list(rawData.values())[0][3]['data']

    filterAv = auxFilterData['availableFilters']

    name2comp = {'Liga Nacional': 'LACB', 'Copa de España': 'COPA', 'Supercopa': 'SCOPA'}
    for v in filterAv['competitions']:
        cName = v['name']
        cId = str(v['id'])
        if cName not in name2comp:
            continue
        result['compKey2compId'][name2comp[cName]] = cId
        result['compId2compKey'][cId] = name2comp[cName]

    s: dict
    for s in filterAv['seasons']:
        sId = str(s['id'])
        sYear = str(s['startYear'])
        result['seaId2seaYear'][sId] = sYear
        result['seaYear2seaId'][sYear] = sId
        result['seaData'][sYear] = s

    auxCurrData = auxFilterData['selectedFilters']
    result['currFilters'].update(auxCurrData)
    result['currFilters']['seaYear'] = result['seaId2seaYear'][str(auxCurrData['season'])]
    result['currFilters']['compKey'] = result['compId2compKey'][str(auxCurrData['competition'])]
    result['currFilters']['seaId'] = str(auxCurrData['season'])
    result['currFilters']['compId'] = str(auxCurrData['competition'])

    return result


def procesaMDcalTeams2InfoEqs(rawData: dict) -> Dict[str, Dict]:
    result = {'eqData': {}, 'eqAbrev2eqId': {}, 'seq2eqId': {}, 'seq2eqAbrev': {}, 'eqId2eqAbrev': {}}

    eqDataTxlat = {'id': 'calId', 'clubId': 'id', 'fullName': 'nomblargo', 'shortName': 'nombcorto',
                   'abbreviatedName': 'abrev',
                   'logo': 'icono', 'secondaryLogo': 'iconoSec'}
    auxFilterData: dict = list(rawData.values())[0][3]['data']

    auxTeamsData: dict = auxFilterData['teams']

    for seq, eq in enumerate(auxTeamsData):
        eqAbrev = eq['abbreviatedName']
        eqId = str(eq['clubId'])
        result['seq2eqId'][str(seq)] = eqId
        result['seq2eqAbrev'][str(seq)] = eqAbrev
        result['eqAbrev2eqId'][eqAbrev] = eqId
        result['eqId2eqAbrev'][eqId] = eqAbrev
        result['eqData'][eqId] = {eqDataTxlat.get(k, k): v for k, v in eq.items()}

    return result


def processMDcalFl2Info(rawData: dict, infoMDequipos: dict) -> Dict[str, Dict]:
    """
    Saca la información de calendario del script que lleva embebida la página del calendario
    :param rawData:
    :return:
    """

    result = {}

    auxRounds: dict = list(rawData.values())[0][3]['data']['rounds']

    for r in auxRounds:
        infoRound = {'partidos': {}, 'pendientes': set(), 'jugados': set(), 'equipos': set(), 'idEmparej': set()}

        infoRound.update(MDround2roundData(r))

        for g in r['matches']:
            partPendiente: bool = g['matchStatus'] != 'FINALIZED'
            datosPart = {'fechaPartido': pd.to_datetime(g['startDateTime']),
                         'pendiente': partPendiente, 'equipos': {}, 'resultado': {}}
            datosPart['partido'] = g['id']

            for loc in LocalVisitante:
                datosEq = {}
                clavTrad = LV2HA[loc]
                clavTradOther = LV2HA[OtherLoc(loc)]

                eqSeq = g[clavTrad + 'Team'].split(':')[-1]
                datosEq['id'] = infoMDequipos['seq2eqId'][eqSeq]
                datosEq.update(infoMDequipos['eqData'][datosEq['id']])
                if not partPendiente:
                    datosEq['puntos'] = g[clavTrad + 'TeamScore']
                    datosEq['haGanado'] = datosEq['puntos'] > g[clavTradOther + 'TeamScore']
                    datosPart['resultado'][loc] = datosEq['puntos']
                    infoRound['equipos'].add(datosEq['abrev'])
                datosPart['equipos'][loc] = datosEq

            datosPart['loc2abrev'] = {k: v['abrev'] for k, v in datosPart['equipos'].items()}
            datosPart['abrev2loc'] = {v['abrev']: k for k, v in datosPart['equipos'].items()}
            datosPart['participantes'] = {v['abrev'] for v in datosPart['equipos'].values()}
            datosPart['claveEmparejamiento'] = ",".join(sorted([str(v['id']) for v in datosPart['equipos'].values()]))

            infoRound['idEmparej'].add(datosPart['claveEmparejamiento'])

            infoRound['partidos'][datosPart['claveEmparejamiento']] = datosPart
            if partPendiente:
                infoRound['pendientes'].add(datosPart['claveEmparejamiento'])
            else:
                infoRound['jugados'].add(datosPart['claveEmparejamiento'])

        result[infoRound['jornada']] = infoRound

    return result


rondaId2fasePlayOff: dict = {291: 'final', 293: 'cuartos de final', 292: 'semifinal'}


def MDround2roundData(jornada: dict) -> dict:
    result = {'jorId': jornada['id'], 'jornada': jornada['roundNumber'], 'jornadaMD': jornada['roundNumber'],
              'esPlayOff': (jornada['subphase'] is not None), 'fasePlayOff': None, 'partRonda': None}

    if result['esPlayOff']:
        result['fasePlayOff'] = rondaId2fasePlayOff[jornada['subphase']['id']]
        result['partRonda'] = jornada['subphase']['subphaseNumber']
        result['jornada'] = numPartidoPO2jornada(result['fasePlayOff'], result['partRonda'])

    result['infoJornada'] = infoJornada(jornada=result['jornada'], esPlayOff=result['esPlayOff'],
                                        fasePlayOff=result['fasePlayOff'],
                                        partRonda=result['partRonda'])

    return result


def procesaMDresInfoPeriodos(rawData: dict) -> Optional[Dict[str, List[Tuple[int, int]]]]:
    if len(rawData) == 0:
        return None

    for data in rawData.values():
        datosPeriodos: dict = data[3].get('initialMatchHeader', {}).get('quarterScores', None)

        if datosPeriodos is None:
            return None

        result = {'parciales': [(perData['home'], perData['away']) for perData in
                                sorted(datosPeriodos, key=lambda d: d['quarter'])]}
        result['acumulados'] = []
        locAc, visAc = (0, 0)
        for loc, vis in result['parciales']:
            acum = (locAc + loc, visAc + vis)
            result['acumulados'].append(acum)
            locAc, visAc = acum

        return result
    return None


def procesaMDresEstadsCompar(rawData: dict) -> Optional[List[Tuple[int, int]]]:
    tradClaves = {'freeThrows': "T1", 'twoPointers': "T2", 'threePointers': "T3", 'fieldGoals': "TC",
                  'defensiveRebounds': "R-D", 'offensiveRebounds': "R-O", 'rebounds': "R-T", 'assists': "A",
                  'steals': "BR",
                  'turnovers': "BP", 'personalFouls': "FP-C", 'timeOuts': "TM", 'pointsOffTurnover': "PtrasPer",
                  'paintPoints': "Ppint", 'secondChancePoints': "PsegOp", 'fastBreakPoints': "Pcontr",
                  'benchPoints': "Pbanq"}

    resultado = {'periodos': {}}

    if len(rawData) > 1:
        return None

    auxData: dict = list(rawData.values())[0][3]['initialMatchStatsComparative']

    resultado['totales'] = auxProcessEstadCompar(auxData['global'], tradClaves)
    for dataQ in auxData['statsByQuarters']:
        resultado['periodos'][dataQ['quarter']] = auxProcessEstadCompar(dataQ['stats'], tradClaves)

    return resultado


def auxProcessEstadCompar(data: dict, tradClaves: Dict[str, str]) -> Dict[str, Dict[str, int]]:
    result = {loc: {} for loc in LocalVisitante}

    for clave, valores in data.items():
        for loc in LocalVisitante:
            infoLoc = valores[LV2HA[loc]]
            claveTrad = tradClaves.get(clave, clave)
            if infoLoc['subtitle'] == '$undefined':
                if ':' in infoLoc['title']:
                    result[loc][claveTrad] = ProcesaTiempo(infoLoc['title'])
                else:
                    result[loc][claveTrad] = int(infoLoc['title'])
            else:
                for subc, valor in zip('CI', infoLoc['subtitle'].split('/')):
                    claveFin = f"{claveTrad}-{subc}"
                    result[loc][claveFin] = int(valor)

    return result


def procesaMDresInfoRachas(rawData: dict):
    tradClaves = {'bestScoreRun': 'mejorRacha', 'maxDifference': 'maxVentaja', 'timeAhead': 'tiempoDelante',
                  'leadChanges': 'cambiosLider'}
    if len(rawData) > 1:
        return None

    auxData: dict = list(rawData.values())[0][3]['initialLeadTracker']['stats']

    result = auxProcessEstadCompar(auxData, tradClaves)

    return result


def procesaMDresCartaTiro(rawData: dict):
    EXCLUDESCTIRO = {'playerName', 'playerNumber', 'playerImage', 'playerLicenseId'}
    resultado = createDictOfType(LocalVisitante, list)

    if len(rawData) > 1:
        return None

    auxData: dict = list(rawData.values())[0][3]['initialShotmap']['shots']

    for shot in auxData:
        loc = IsH2LOC[shot['isHome']]

        auxShot = copyDictWithTranslation(shot, excludes=EXCLUDESCTIRO)
        auxShot['seg'] = cuartYtiempo2segs(cuarto=shot['quarter'], mins=shot['minute'], segs=shot['second'])
        auxShot['codigoJug'] = str(shot['playerLicenseId'])

        resultado[loc].append(auxShot)

    return resultado


def jugadaKey2sort(jugKey: Tuple[int, Optional[int]]) -> Tuple[int, int]:
    return (jugKey[0], 0 if jugKey[1] is None else jugKey[1])


def jugadaKey2str(jugKey):
    plType = jugKey[0]
    plTag = jugKey[1]
    auxTag = "None" if plTag is None else f"{plTag:4}"

    res = f"({plType:3},{auxTag})"
    return res


def jugada2str(play: str) -> str:
    def jugada2subject(play):

        licType = play['licenseType']
        if licType == 202:
            return f"{play['playerName']}"
        if licType is None:
            return f"Equipo"
        res = f"{play}"
        logging.warning("jugada2subject: licenseType desconocido '%s'. %s", licType, res)

        return res

    playKey: Tuple[int, Optional[int]] = (play['playType'], play['playTag'])
    loc = "L" if play['local'] else "V"  # IsH2LOC[play['local']]
    tiempoJug = f"Q:{play['quarter']} {play['minute']:02}:{play['second']:02}"

    playDescr = jugadaTag2Desc.get(playKey, "Jugada desc")

    result = f"[{play['order']:6}] {tiempoJug} {jugadaKey2str(playKey)} {loc:3} {playDescr} {jugada2subject(play)}"

    return result


def jugadaSort(p, reverse=False) -> Tuple[int, int, int]:
    orderMod = -1 if reverse else 1

    return orderMod * p['quarter'], orderMod * -p['minute'], orderMod * -p['second']


def procesaMDjugadas(rawData: dict):
    EXCLUDES = {'team', 'playerImage', 'playerStats', 'playerName', 'playerNumber', 'playerLicenseId'}

    if len(rawData) > 1:
        return None

    listaJugs: List[Dict] = list(rawData.values())[0][3]['initialMatchPlayByPlay']['plays']
    resultado = {'jugadas': [], 'clavesDesconocidas': {}, 'contadores': {}, 'contConocidas': {True: 0, False: 0}}

    logging.debug("Listado de jugadas")
    for play in sorted(listaJugs, key=jugadaSort, reverse=True):
        jugada = copyDictWithTranslation(play, excludes=EXCLUDES)
        jugada['codigoJug'] = str(play['playerLicenseId'])
        jugada['seg'] = cuartYtiempo2segs(cuarto=play['quarter'], mins=play['minute'], segs=play['second'])

        resultado['jugadas'].append(jugada)

        playKey: Tuple[int, Optional[int]] = (play['playType'], play['playTag'])

        if playKey not in jugadaTag2Desc:
            if playKey not in resultado['clavesDesconocidas']:
                resultado['clavesDesconocidas'][playKey] = []
            resultado['clavesDesconocidas'][playKey].append(play)

        if playKey not in resultado['contadores']:
            resultado['contadores'][playKey] = 0
        resultado['contadores'][playKey] += 1
        resultado['contConocidas'][playKey in jugadaTag2Desc] += 1

        logging.debug(jugada2str(play))

    return resultado


EQKEYS2ADD = ['clubId', 'fullName', 'shortName', 'abbreviatedName']
BSC2STATKEYS = {'assists': 'A', 'blocks': 'TAP-F', 'defRebounds': 'R-D', 'dunks': 'M', 'foulsDrawn': 'FP-F',
                'freeThrowsAttempted': 'T1-I', 'freeThrowsMade': 'T1-C',
                'offRebounds': 'R-O', 'personalFouls': 'FP-C', 'plusMinus': '+/-', 'points': 'P',
                'rating': 'V', 'receivedBlocks': 'TAP-C',
                'steals': 'BR', 'threePointersAttempted': 'T3-I', 'threePointersMade': 'T3-C', 'totalRebounds': 'REB-T',
                'turnovers': 'BP', 'twoPointersAttempted': 'T2-I',
                'twoPointersMade': 'T2-C', 'isStarted': 'titular'}  # 'playTime': 'Segs' ,'onCourt','player',

PLYSTATS2KEYS = {'firstInitialAndLastName': 'nombre',
                 'shirtNumber': 'dorsal',
                 'headshotImageUrl': 'urlFoto',
                 }


def extraeEstadsPeriodo(data: dict):
    ESTADS2IGNORE = {'onCourt', 'player', 'playTime', 'isStarted'}
    result = copyDictWithTranslation(data, BSC2STATKEYS, ESTADS2IGNORE)

    if 'playTime' in data:
        result['Segs'] = ProcesaTiempo(data['playTime'])

    return result


def procesaMDboxscore(rawData: dict):
    EXCLUDEPLAYSTATS = {'id', 'headshotImageAlt', 'firstName'}

    resultado = {'equipos': {}, 'totales': {}, 'noAsig': {},
                 'infoJugs': dict.fromkeys(LocalVisitante, {})}

    if len(rawData) > 1:
        return None

    boxScoreData = list(rawData.values())[0][3]['initialStatistics']
    periodos = [s['quarter'] for s in boxScoreData['teamBoxscores'][0]['statsByPeriods'] if s['quarter'] != 0]
    resultado['cancha'] = boxScoreData['arena']
    resultado['asistencia'] = boxScoreData['attendance']
    resultado['arbitros']: set = set(boxScoreData['referees'])
    resultado['jugadores']: dict = {}
    resultado['porCuarto']: dict = dict.fromkeys(periodos, dict.fromkeys(['totales', 'noAsig', 'jugadores'], {}))

    for loc, datosEq in zip(LocalVisitante, boxScoreData['teamBoxscores']):
        resultado['equipos'][loc] = {k: datosEq['team'][k] for k in EQKEYS2ADD}
        resultado['equipos'][loc]['jugadores']: set = set()
        resultado['equipos'][loc]['entrenador'] = datosEq['headCoach']
        resultado['equipos'][loc]['ayudantes'] = set(datosEq['assistantCoaches'])

        for dataPer in datosEq['statsByPeriods']:
            periodo = dataPer['quarter']
            statsQ = dataPer['stats']
            datosTotal = extraeEstadsPeriodo(statsQ['total'])
            datosTotal['Segs'] = 0
            datosNoAsig = extraeEstadsPeriodo(statsQ['team'])
            for dataJug in statsQ['players']:
                playerData = copyDictWithTranslation(dataJug['player'], PLYSTATS2KEYS, EXCLUDEPLAYSTATS)
                playerData['esLocal'] = loc == "Local"

                playerId = str(dataJug['player']['id'])
                playerData['codigo'] = playerId
                resultado['equipos'][loc]['jugadores'].add(playerId)

                dJug = extraeEstadsPeriodo(dataJug)
                datosTotal['Segs'] += dJug['Segs']

                if periodo == 0:
                    playerData['titular'] = dataJug['isStarted']
                    resultado['infoJugs'][loc][playerId] = playerData

                    resultado['jugadores'][playerId] = dJug
                else:
                    resultado['porCuarto'][periodo]['jugadores'][playerId] = dJug

            if periodo == 0:
                resultado['totales'][loc] = datosTotal
                resultado['noAsig'][loc] = datosNoAsig
            else:
                resultado['porCuarto'][periodo]['totales'][loc] = datosTotal
                resultado['porCuarto'][periodo]['noAsig'][loc] = datosNoAsig

    return resultado


def cuartYtiempo2segs(cuarto: int, mins: int, segs: int) -> int:
    resSegs = 60 * mins + segs

    if cuarto == 0:
        return resSegs

    if cuarto <= 4:
        return 600 * cuarto - resSegs

    return 2400 + 300 * (cuarto - 4) - resSegs


def procesaMDavailableContent(rawData: dict) -> Optional[Dict[str, bool]]:
    TRAVCONTENT = {'overview': 'resumen', 'playbyplay': 'jugadas', 'boxscore': 'estadisticas'}

    if len(rawData) == 0:
        return None

    for data in rawData.values():

        avContentData = data[3].get('initialMatchHeader', {}).get('availableContent', None)
        if avContentData is None:
            continue
        resultado = copyDictWithTranslation(avContentData, translation=TRAVCONTENT)
        return resultado

    return None


def procesaMDresDatosPartido(rawData: dict) -> Optional[Dict[str, Dict]]:
    TRTEAMDATA = {'abbreviatedName': 'Abrev', }  # ,
    EXTEAMDATA = {'id', 'clubId', 'primaryColorHex', 'textColorHex', 'shirtColor', 'displayColor', 'displayTextColor',
                  'logoAlt', 'logo', 'secondaryLogo', }
    if len(rawData) == 0:
        return None

    for data in rawData.values():
        resultado = {}
        datosPartido: dict = data[3].get('initialMatchHeader', None)

        if datosPartido is None:
            return None

        resultado['partidoId'] = str(datosPartido['matchId'])
        resultado['fechaHora'] = pd.to_datetime(datosPartido['start'])
        resultado['compoId'] = str(datosPartido['competitionId'])
        resultado['equipos'] = {}
        for auxLoc, teamData in datosPartido['teams'].items():
            loc = HA2LV[auxLoc]
            infoTeam = copyDictWithTranslation(teamData, translation=TRTEAMDATA, excludes=EXTEAMDATA)
            infoTeam.update({TRTEAMDATA.get(k, k): str(teamData[k]) for k in ['id', 'clubId']})
            infoTeam['Nombres'] = {teamData[k] for k in {'fullName', 'shortName'}}
            infoTeam['Logos'] = {teamData[k] for k in {'logo', 'secondaryLogo'}}

            infoTeam['Puntos'] = datosPartido[f"current{auxLoc.capitalize()}Score"]
            resultado['equipos'][loc] = infoTeam

        for loc in LocalVisitante:
            resultado['equipos'][loc]['haGanado'] = resultado['equipos'][loc]['Puntos'] > \
                                                    resultado['equipos'][OtherLoc(loc)]['Puntos']
            resultado['equipos'][loc]['esLocal'] = loc == "Local"

        return resultado

    return None

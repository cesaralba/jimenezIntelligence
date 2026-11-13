import logging
import re
from typing import Dict, Optional, Any, List, Tuple

import pandas as pd
from CAPcore.Misc import copyDictWithTranslation, removeAccents

from SMACB.Constants import LocalVisitante, OtherLoc
from Utils.ParseoData import ProcesaTiempo, parseFecha, parseaAltura
from Utils.ProcesaMDACB.Calendario import LV2HA

HA2LV = {'home': 'Local', 'away': 'Visitante'}
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


def jugData2linkInfo(jugData: Dict) -> str:
    dataForLink = [removeAccents(str(jugData['player'][k])) for k in ['firstName', 'lastName', 'id']]

    resultStr = " ".join(dataForLink)
    result = re.sub(r"\s+", "-", resultStr).lower()
    return result


def procesaMDboxscore(rawData: dict):
    EXCLUDEPLAYSTATS = {'id', 'headshotImageAlt', 'firstName'}

    resultado = {'equipos': {}, 'totales': {}, 'noAsig': {},
                 'infoJugs': dict.fromkeys(LocalVisitante, {})}

    if len(rawData) > 1:
        return None

    boxScoreData = next(iter(rawData.values()))[3]['initialStatistics']
    periodos = [s['quarter'] for s in boxScoreData['teamBoxscores'][0]['statsByPeriods'] if s['quarter'] != 0]
    resultado['cancha'] = boxScoreData['arena']
    resultado['asistencia'] = boxScoreData['attendance']
    resultado['arbitros']: set = set(boxScoreData['referees'])
    resultado['jugadores']: dict = {}
    resultado['porCuarto']: dict = dict.fromkeys(periodos, dict.fromkeys(['totales', 'noAsig', 'jugadores'], {}))

    for loc, datosEq in zip(LocalVisitante, boxScoreData['teamBoxscores']):
        resultado['equipos'][loc] = {k: datosEq['team'][k] for k in EQKEYS2ADD}
        resultado['equipos'][loc]['clubId'] = str(resultado['equipos'][loc]['clubId'])
        resultado['equipos'][loc]['jugadores']: set = set()
        resultado['equipos'][loc]['entrenador'] = datosEq['headCoach']
        resultado['equipos'][loc]['ayudantes'] = set(datosEq['assistantCoaches'])

        for dataPer in datosEq['statsByPeriods']:
            periodo = dataPer['quarter']
            datosTotal = extraeEstadsPeriodo(dataPer['stats']['total'])
            datosTotal['Segs'] = 0
            datosNoAsig = extraeEstadsPeriodo(dataPer['stats']['team'])
            for dataJug in dataPer['stats']['players']:
                playerData = copyDictWithTranslation(dataJug['player'], PLYSTATS2KEYS, EXCLUDEPLAYSTATS)
                playerData['esLocal'] = loc == "Local"

                playerData['codigo'] = str(dataJug['player']['id'])
                resultado['equipos'][loc]['jugadores'].add(playerData['codigo'])

                dJug = extraeEstadsPeriodo(dataJug)
                datosTotal['Segs'] += dJug['Segs']

                if periodo == 0:
                    playerData['titular'] = dataJug['isStarted']
                    playerData['personaURLpart'] = jugData2linkInfo(dataJug)

                    resultado['infoJugs'][loc][playerData['codigo']] = playerData

                    resultado['jugadores'][playerData['codigo']] = dJug
                else:
                    resultado['porCuarto'][periodo]['jugadores'][playerData['codigo']] = dJug

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
            infoTeam['Nombres'] = {teamData[k] for k in ['fullName', 'shortName']}
            infoTeam['Logos'] = {teamData[k] for k in ['logo', 'secondaryLogo']}

            infoTeam['Puntos'] = datosPartido[f"current{auxLoc.capitalize()}Score"]
            resultado['equipos'][loc] = infoTeam

        for loc in LocalVisitante:
            resultado['equipos'][loc]['haGanado'] = resultado['equipos'][loc]['Puntos'] > \
                                                    resultado['equipos'][OtherLoc(loc)]['Puntos']
            resultado['equipos'][loc]['esLocal'] = loc == "Local"

        return resultado

    return None


def procesaMDfichJugPlayData(rawData: dict) -> Dict[str, Any]:
    result = {}
    result['sinDatos'] = False

    jugData = list(rawData.values())[0][3]['playerData']
    scJugData: Dict[str, Any] = jugData['playerData']

    CLASSROOT2KEYS = {'nationality': 'nacionalidad', 'licensing': 'licencia', 'pronunciationUrl': 'audioURL',
                      'birthPlace': 'NacLugar', 'birthCountry': 'NacPais', }
    CLASSROOTEXCL = {'player', 'birthDate', 'height', 'youtube', 'instagram', 'twitter', 'facebook', 'tiktok',
                     'currentTeam', 'playerNumber', 'isLicenseActive'}
    CLASSPLAYER2KEYS = {'firstInitialAndLastName': 'alias', 'nickname': 'nombre', 'gameRole': 'posicion',
                        'shirtNumber': 'dorsal'}
    CLASSPLAYEREXCL = {'id', 'headshotImageUrl', 'headshotImageNoBackgroundUrl', 'headshotImageAlt', 'fullBodyImageUrl',
                       'fullBodyImageNoBackgroundUrl', 'isLicenseActive', 'editionId'}
    dataFromRootClass = copyDictWithTranslation(scJugData, translation=CLASSROOT2KEYS, excludes=CLASSROOTEXCL)
    dataFromRootClass['lugarNac'] = f"{scJugData['birthPlace']}, {scJugData['birthCountry']}"
    dataFromRootClass['fechaNac'] = parseFecha(scJugData['birthDate'])
    dataFromRootClass['altura'] = parseaAltura(scJugData['height'])

    result.update(dataFromRootClass)

    scPlayer: Dict[str, Any] = scJugData['player']
    scPlayer['nombresConocidos'] = {scPlayer['firstInitialAndLastName'], scPlayer['nickname']}
    scPlayer['fotos'] = {scPlayer['headshotImageUrl'], scPlayer['fullBodyImageUrl']}

    dataFromPlayer = copyDictWithTranslation(scPlayer, translation=CLASSPLAYER2KEYS, excludes=CLASSPLAYEREXCL)

    result.update(dataFromPlayer)

    scClub: Dict[str, Any] = scJugData['currentTeam']
    result['ultClub'] = str(scClub['clubId'])

    return result


IsH2LOC = dict(zip([True, False], LocalVisitante))


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
    resultado = dict.fromkeys(LocalVisitante, [])

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
    (106, 1): "Pér - pasos",
    (106, 2): 'Pér - 3" zona',
    (106, 7): "Pér - final pos",
    (106, 8): 'Pér - infracción 8"',
    (106, 9): 'Pér - final posesión',
    (106, 10): 'Pér - 5" saque',
    (106, 11): "Pér - balón retenido",
    (106, 12): "Pér - mal pase",
    (106, 13): "Pér - balón perdido",
    (106, 14): "Pér - dobles",
    (106, 15): "Pér - campo atrás",

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
    (121, None): "Comienzo periodo",
    (123, None): "Final partido",
    (159, None): "Falta pers 0TL",
    (160, None): "Falta pers 1TL",
    (161, None): "Falta pers 2TL",
    (162, None): "Falta pers 3TL",
    (165, None): "Falta antideportiva",
    (166, None): "Falta antideportiva",
    (167, None): "Falta antideportiva (ataque?)",
    (168, None): "Falta antideportiva compensada",
    (173, None): "Falta técnica compensada",
    (178, None): "Salto ganado",
    (179, None): "Salto perdido",

    (200, None): "Descalificante partido",

    (406, None): "Rev - Tipo de tiro",
    (407, None): "Rev - Canasta válida",
    (408, None): "Rev - Reloj posesión",
    (409, None): "Rev - Reloj de partido",
    (410, None): "Rev - Enfrentamiento",
    (411, None): "Rev - Tipo de falta",
    (412, None): "Rev - violación",
    (413, None): "Rev - Ult jug tocar",
    (414, None): "Rev - Acción jugador",
    (415, None): "Rev - Cambios",
    (416, None): "Challenge Ent loc",
    (417, None): "Challenge Ent vis",

    (533, None): "Mate fallado",
    (537, None): "Falta técnica 1TL",
    (540, None): "Técnica entrenador",
    (543, None): "Técnica entrenador compensada",
    (544, None): "Técnica banquillo",
    (547, None): "Técnica banquillo compensada",
    (599, None): "Entra a pista (quint inicial)",
    (748, None): "Challenge ganado",
    (749, None): "Challenge perdido",
}


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
            return "Equipo"
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
    resultado = {'jugadas': [], 'clavesDesconocidas': {}, 'contadores': {}, 'infoJugadores': {},
                 'contConocidas': {True: 0, False: 0}}

    logging.debug("Listado de jugadas")
    for play in sorted(listaJugs, key=jugadaSort, reverse=True):
        jugada = copyDictWithTranslation(play, excludes=EXCLUDES)
        jugada['codigoJug'] = str(play['playerLicenseId'])
        jugada['seg'] = cuartYtiempo2segs(cuarto=play['quarter'], mins=play['minute'], segs=play['second'])

        resultado['jugadas'].append(jugada)

        playKey: Tuple[int, Optional[int]] = play2key(play)

        if playKey not in jugadaTag2Desc:
            if playKey not in resultado['clavesDesconocidas']:
                resultado['clavesDesconocidas'][playKey] = []
            resultado['clavesDesconocidas'][playKey].append(play)

        if playKey not in resultado['contadores']:
            resultado['contadores'][playKey] = 0
        resultado['contadores'][playKey] += 1
        resultado['contConocidas'][playKey in jugadaTag2Desc] += 1

        if jugada['codigoJug'] not in resultado['infoJugadores']:
            resultado['infoJugadores'][jugada['codigoJug']] = {k: play[k] for k in ['playerName', 'playerNumber']}
        logging.debug(jugada2str(play))

    return resultado


def play2key(play: dict) -> Tuple[int, Optional[int]]:
    return (play['playType'], play['playTag'])

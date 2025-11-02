from typing import Dict

import pandas as pd

from SMACB.Constants import LocalVisitante, OtherLoc, numPartidoPO2jornada, infoJornada


def procesaMDfl2calendarIDs(rawData: dict) -> Dict[str, Dict]:
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


def procesaMDteams2InfoEqs(rawData: dict) -> Dict[str, Dict]:
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


def processMDfl2InfoCal(rawData: dict,infoMDequipos:dict) -> Dict[str, Dict]:
    """
    Saca la información de calendario del script que lleva embebida la página del calendario
    :param rawData:
    :return:
    """


    result = {}

    LV2HA = {'Local': 'home', 'Visitante': 'away'}

    auxFilterData: dict = list(rawData.values())[0][3]['data']
    auxRounds: dict = auxFilterData['rounds']

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

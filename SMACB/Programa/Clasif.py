from collections import namedtuple, defaultdict
from decimal import Decimal
from typing import Optional, Any, Set, List, Tuple, Dict

from CAPcore.Misc import cmp

from SMACB.Constants import LocalVisitante, OtherLoc
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import anyElement

infoClasifEquipoLR = namedtuple('infoClasifEquipoLR',
                                ['Jug', 'V', 'D', 'Pfav', 'Pcon', 'Jjug', 'CasaFuera', 'idEq', 'nombresEq', 'abrevsEq',
                                 'nombreCorto', 'abrevAusar', 'ratioVict', 'sumaCoc'])

infoSerieEquipoPO = namedtuple('infoSerieEquipoPO',
                               ['Fase', 'idRival', 'Jug', 'V', 'D', 'Pfav', 'Pcon', 'victoria', 'localia'])

infoEquipoPO = namedtuple('infoEquipoPO', ['idEq', 'fases'])

infoClasifBase = namedtuple(typename='infoClasifEquipo', field_names=['Jug', 'V', 'D', 'Pfav', 'Pcon'],
                            defaults=(0, 0, 0, 0, 0))
infoClasifComplPareja = namedtuple(typename='infoClasifComplPareja',
                                   field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                   defaults=(0, 0, 0, 0, 0, Decimal(0.000)))
infoClasifComplMasD2 = namedtuple(typename='infoClasifComplMasD2',
                                  field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'EmpPfav', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                  defaults=(0, 0, 0, 0, 0, 0, Decimal(0.000)))


def entradaClas2kVict(ent: infoClasifEquipoLR, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    del kargs
    result = ent.V
    return result


def entradaClas2kRatioVict(ent: infoClasifEquipoLR, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    del kargs
    result = ent.ratioVict
    return result


def entradaClas2kBasic(ent: infoClasifEquipoLR, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    del kargs

    result = (ent.V, ent.ratioVict, ent.Pfav - ent.Pcon, ent.Pfav, ent.sumaCoc)
    return result


def entradaClas2kEmpatePareja(ent: infoClasifEquipoLR, datosLR: dict) -> infoClasifComplPareja:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.idEq]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'LRDifP': auxLR.Pfav - auxLR.Pcon,
           'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplPareja(**aux)

    return result


def entradaClas2kEmpateMasD2(ent: infoClasifEquipoLR, datosLR: dict) -> infoClasifComplMasD2:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.idEq]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'EmpPfav': ent.Pfav,
           'LRDifP': auxLR.Pfav - auxLR.Pcon, 'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplMasD2(**aux)

    return result


def calculaClasifEquipoLR(dataTemp: TemporadaACB, idEq: str, fecha: Optional[Any] = None,
                          gameList: Optional[set[str]] = None
                          ) -> infoClasifEquipoLR:
    """
    Extrae los datos necesarios para calcular la clasificación (solo liga regular) de un equipo hasta determinada
    fecha
    :param abrEq: Abreviatura del equipo en cuestión, puede ser cualquiera de las que haya tenido
    :param fecha: usar solo los partidos ANTERIORES a la fecha
    :return: diccionario con los datos calculados
    """
    auxResult = defaultdict(int)
    auxResult['Jjug'] = set()
    auxResult['auxCasaFuera'] = {'Local': defaultdict(int), 'Visitante': defaultdict(int)}
    auxResult['CasaFuera'] = {}
    auxResult['sumaCoc'] = Decimal(0)

    urlGamesFull = dataTemp.extractGameList(fecha=fecha, idEquipos={idEq}, playOffStatus=False)
    urlGames = urlGamesFull if gameList is None else urlGamesFull.intersection(gameList)
    partidosAcontar = [dataTemp.Partidos[pURL].DatosSuministrados for pURL in urlGames]

    for datosCal in partidosAcontar:
        auxResult['Jjug'].add(int(datosCal['jornada']))

        id2loc = datosCal.get('id2loc', {str(datosCal['equipos'][loc]['id']): loc for loc in LocalVisitante})

        locEq = id2loc[idEq]
        locRival = OtherLoc(locEq)

        datosEq = datosCal['equipos'][locEq]
        datosRival = datosCal['equipos'][locRival]
        claveRes = 'V' if datosEq['haGanado'] else 'D'

        auxResult['Jug'] += 1
        auxResult[claveRes] += 1
        auxResult['auxCasaFuera'][locEq][claveRes] += 1

        auxResult['Pfav'] += datosEq['puntos']
        auxResult['Pcon'] += datosRival['puntos']
        auxResult['sumaCoc'] += (Decimal(datosEq['puntos']) / Decimal(datosRival['puntos'])).quantize(Decimal('.001'))

    auxResult['idEq'] = idEq
    auxResult['nombresEq'] = dataTemp.Calendario.tradEquipos['i2n'][idEq]
    auxResult['abrevsEq'] = dataTemp.Calendario.tradEquipos['i2c'][idEq]
    auxResult['nombreCorto'] = sorted(auxResult['nombresEq'], key=len)[0]
    auxResult['abrevAusar'] = anyElement(auxResult['abrevsEq'])

    for k in ['Jug', 'V', 'D', 'Pfav', 'Pcon']:
        if k not in auxResult:
            auxResult[k] = 0
    for loc in LocalVisitante:
        auxResult['CasaFuera'][loc] = infoClasifBase(**auxResult['auxCasaFuera'][loc])
    auxResult.pop('auxCasaFuera')
    auxResult['ratioVict'] = auxResult['V'] / auxResult['Jug'] if auxResult['Jug'] else 0.0
    result = infoClasifEquipoLR(**auxResult)
    return result


def calculaClasifLigaLR(dataTemp: TemporadaACB, fecha=None, idList: Optional[Set[str]] = None, parcial: bool = False,
                        datosLR=None
                        ) -> List[infoClasifEquipoLR]:
    teamIdList = idList
    if idList is None:
        teamIdList = set(dataTemp.Calendario.tradEquipos['i2c'].keys())

    funcKey = entradaClas2kBasic

    gameList = dataTemp.extractGameList(fecha=fecha, idEquipos=teamIdList, playOffStatus=False)

    datosClasifEquipos: List[infoClasifEquipoLR] = [
        calculaClasifEquipoLR(dataTemp, idEq=eq, fecha=fecha, gameList=gameList) for eq in teamIdList]

    if datosLR is None:
        datosLR = {x.idEq: x for x in datosClasifEquipos}

    if parcial:  # Grupo de empatados
        numEqs = len(idList)
        if len(gameList) != numEqs * (numEqs - 1):  # No han jugado todos contra todos I-V
            # Estadistica básica con los partidos de LR
            funcKey = entradaClas2kBasic
            datosClasifEquipos = [datosLR[idEq] for idEq in idList]

        else:  # Han jugado todos contra todos I-V
            funcKey = entradaClas2kEmpatePareja if len(idList) == 2 else entradaClas2kEmpateMasD2
    else:  # Todos los equipos
        partsJug = {i.Jug for i in datosClasifEquipos}
        funcKey = entradaClas2kVict if len(partsJug) == 1 else entradaClas2kRatioVict

    resultInicial = sorted(datosClasifEquipos, key=lambda x: funcKey(x, datosLR), reverse=True)

    resultFinal = []
    agrupClasif = defaultdict(set)
    for datosEq in resultInicial:
        idEq = datosEq.idEq
        kClasif = funcKey(datosEq, datosLR)
        agrupClasif[kClasif].add(idEq)

    for k in sorted(agrupClasif, reverse=True):
        idK = agrupClasif[k]
        if len(idK) == 1:
            for idEq in idK:
                resultFinal.append(datosLR[idEq])
        else:
            desempate = calculaClasifLigaLR(dataTemp=dataTemp, fecha=fecha, idList=idK, parcial=True,
                                            datosLR=datosLR)
            for sc in desempate:
                resultFinal.append(datosLR[sc.idEq])

    result = resultFinal
    return result


def calculaEstadoLigaPO(dataTemp: TemporadaACB, fecha=None) -> Dict[str, infoEquipoPO]:
    auxResult = defaultdict(lambda: {
        'fases': defaultdict(lambda: {'Jug': 0, 'V': 0, 'D': 0, 'Pfav': 0, 'Pcon': 0, 'victoria': [], 'localia': []})})

    idList = set(dataTemp.Calendario.tradEquipos['i2c'].keys())

    gameList = dataTemp.extractGameList(fecha=fecha, idEquipos=idList, playOffStatus=True)

    for p in sorted(gameList, key=lambda p: dataTemp.Partidos[p].fechaPartido):
        partido = dataTemp.Partidos[p]
        fase = (partido.infoJornada if hasattr(partido, 'infoJornada') else dataTemp.Calendario[partido.jornada][
            'infoJornada']).fasePlayOff.lower()

        for eq, data in partido.Equipos.items():
            dataOther = partido.Equipos[OtherLoc(eq)]
            idEq = data['id']
            auxResult[idEq]['idEq'] = idEq
            auxResult[idEq]['fases'][fase]['Fase'] = fase
            auxResult[idEq]['fases'][fase]['idRival'] = dataOther['id']
            auxResult[idEq]['fases'][fase]['Jug'] += 1
            auxResult[idEq]['fases'][fase]['V'] += int(data['haGanado'])
            auxResult[idEq]['fases'][fase]['D'] += int(dataOther['haGanado'])
            auxResult[idEq]['fases'][fase]['Pfav'] += data['Puntos']
            auxResult[idEq]['fases'][fase]['Pcon'] += dataOther['Puntos']
            auxResult[idEq]['fases'][fase]['victoria'].append(data['haGanado'])
            auxResult[idEq]['fases'][fase]['localia'].append(eq == "Local")

    result = {}
    for idEq, estadoEq in auxResult.items():
        series = {k: infoSerieEquipoPO(**v) for k, v in estadoEq['fases'].items()}
        result[idEq] = infoEquipoPO(idEq=idEq, fases=series)

    return result


def infoGanadorEmparej(data: List[Tuple[str, infoClasifComplPareja]]):
    v1 = data[0][1]
    v2 = data[1][1]

    if hasattr(v1, '_fields'):  # namedtuple
        idx = v1._fields
        for t in idx:
            aux1 = getattr(v1, t)
            aux2 = getattr(v2, t)
            auxcmp = cmp(aux1, aux2)
            if auxcmp == 0:
                continue
            if auxcmp > 0:
                return (data[0][0], t, aux1 - aux2)
            return (data[1][0], t, aux2 - aux1)

    else:  # iterable Asume que son del mismo tipo pero no se preocupa en comprobarlo
        idx = range(len(v1))
        for t in idx:
            aux1 = v1[t]
            aux2 = v2[t]
            auxcmp = cmp(aux1, aux2)
            if auxcmp == 0:
                continue
            if auxcmp > 0:
                return (data[0][0], t, aux1 - aux2)
            return (data[1][0], t, aux2 - aux1)

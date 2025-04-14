from collections import namedtuple, defaultdict
from decimal import Decimal
from typing import Optional, Any, Set, List, Tuple

from CAPcore.Misc import onlySetElement

from SMACB.Constants import LocalVisitante, OtherLoc
from SMACB.TemporadaACB import TemporadaACB

infoClasifEquipo = namedtuple('infoClasifEquipo',
                              ['Jug', 'V', 'D', 'Pfav', 'Pcon', 'Jjug', 'CasaFuera', 'idEq', 'nombresEq', 'abrevsEq',
                               'nombreCorto', 'abrevAusar', 'ratioVict', 'sumaCoc'])
infoClasifBase = namedtuple(typename='infoClasifEquipo', field_names=['Jug', 'V', 'D', 'Pfav', 'Pcon'],
                            defaults=(0, 0, 0, 0, 0))
infoClasifComplPareja = namedtuple(typename='infoClasifComplPareja',
                                   field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                   defaults=(0, 0, 0, 0, 0, Decimal(0.000)))
infoClasifComplMasD2 = namedtuple(typename='infoClasifComplMasD2',
                                  field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'EmpPfav', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                  defaults=(0, 0, 0, 0, 0, 0, Decimal(0.000)))


def entradaClas2kVict(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = ent.V
    return result


def entradaClas2kRatioVict(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = ent.ratioVict
    return result


def entradaClas2kBasic(ent: infoClasifEquipo, *kargs) -> tuple:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """

    result = (ent.V, ent.ratioVict, ent.Pfav - ent.Pcon, ent.Pfav, ent.sumaCoc)
    return result


def entradaClas2kEmpatePareja(ent: infoClasifEquipo, datosLR: dict) -> infoClasifComplPareja:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.abrevAusar]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'LRDifP': auxLR.Pfav - auxLR.Pcon,
           'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplPareja(**aux)

    return result


def entradaClas2kEmpateMasD2(ent: infoClasifEquipo, datosLR: dict) -> infoClasifComplMasD2:
    """
    Dado un resultado de Temporada.getClasifEquipo)

    :param ent: lista de equipos (resultado de Temporada.getClasifEquipo)
    :return: tupla (Vict, ratio Vict/Jugados,  Pfavor - Pcontra, Pfavor)
    """
    auxLR = datosLR[ent.abrevAusar]
    aux = {'EmpV': ent.V, 'EmpRatV': ent.ratioVict, 'EmpDifP': ent.Pfav - ent.Pcon, 'EmpPfav': ent.Pfav,
           'LRDifP': auxLR.Pfav - auxLR.Pcon, 'LRPfav': auxLR.Pfav, 'LRSumCoc': auxLR.sumaCoc}
    result = infoClasifComplMasD2(**aux)

    return result


def calculaClasifEquipo(dataTemp: TemporadaACB, abrEq: str, fecha: Optional[Any] = None,
                        gameList: Optional[set[str]] = None
                        ) -> infoClasifEquipo:
    """
    Extrae los datos necesarios para calcular la clasificación (solo liga regular) de un equipo hasta determinada
    fecha
    :param abrEq: Abreviatura del equipo en cuestión, puede ser cualquiera de las que haya tenido
    :param fecha: usar solo los partidos ANTERIORES a la fecha
    :return: diccionario con los datos calculados
    """
    abrevsEq = dataTemp.Calendario.abrevsEquipo(abrEq)
    auxResult = defaultdict(int)
    auxResult['Jjug'] = set()
    auxResult['auxCasaFuera'] = {'Local': defaultdict(int), 'Visitante': defaultdict(int)}
    auxResult['CasaFuera'] = {}
    auxResult['sumaCoc'] = Decimal(0)

    urlGamesFull = dataTemp.extractGameList(fecha=fecha, abrevEquipos={abrEq}, playOffStatus=False)
    urlGames = urlGamesFull if gameList is None else urlGamesFull.intersection(gameList)
    partidosAcontar = [dataTemp.Partidos[pURL].DatosSuministrados for pURL in urlGames]

    for datosCal in partidosAcontar:
        auxResult['Jjug'].add(int(datosCal['jornada']))

        abrevUsada = abrevsEq.intersection(datosCal['participantes']).pop()
        locEq = datosCal['abrev2loc'][abrevUsada]
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

    auxResult['idEq'] = dataTemp.Calendario.tradEquipos['c2i'][abrEq]
    auxResult['nombresEq'] = dataTemp.Calendario.tradEquipos['c2n'][abrEq]
    auxResult['abrevsEq'] = abrevsEq
    auxResult['nombreCorto'] = sorted(auxResult['nombresEq'], key=len)[0]
    auxResult['abrevAusar'] = abrEq

    for k in ['Jug', 'V', 'D', 'Pfav', 'Pcon']:
        if k not in auxResult:
            auxResult[k] = 0
    for loc in LocalVisitante:
        auxResult['CasaFuera'][loc] = infoClasifBase(**auxResult['auxCasaFuera'][loc])
    auxResult.pop('auxCasaFuera')
    auxResult['ratioVict'] = auxResult['V'] / auxResult['Jug'] if auxResult['Jug'] else 0.0
    result = infoClasifEquipo(**auxResult)
    return result


def calculaClasifLiga(dataTemp: TemporadaACB, fecha=None, abrevList: Optional[Set[str]] = None, parcial: bool = False,
                      datosLR=None
                      ) -> List[infoClasifEquipo]:
    teamList = abrevList
    if abrevList is None:
        teamList = {onlySetElement(codSet) for codSet in dataTemp.Calendario.tradEquipos['i2c'].values()}

    funcKey = entradaClas2kBasic

    gameList = dataTemp.extractGameList(fecha=fecha, abrevEquipos=teamList, playOffStatus=False)

    datosClasifEquipos: List[infoClasifEquipo] = [
        calculaClasifEquipo(dataTemp, abrEq=eq, fecha=fecha, gameList=gameList) for eq in teamList]

    if datosLR is None:
        datosLR = {x.abrevAusar: x for x in datosClasifEquipos}

    if parcial:  # Grupo de empatados
        numEqs = len(teamList)
        if len(gameList) != numEqs * (numEqs - 1):  # No han jugado todos contra todos I-V
            # Estadistica básica con los partidos de LR
            funcKey = entradaClas2kBasic
            datosClasifEquipos = [datosLR[abrev] for abrev in abrevList]

        else:  # Han jugado todos contra todos I-V
            funcKey = entradaClas2kEmpatePareja if len(teamList) == 2 else entradaClas2kEmpateMasD2
    else:  # Todos los equipos
        partsJug = {i.Jug for i in datosClasifEquipos}
        funcKey = entradaClas2kVict if len(partsJug) == 1 else entradaClas2kRatioVict

    resultInicial = sorted(datosClasifEquipos, key=lambda x: funcKey(x, datosLR), reverse=True)

    resultFinal = []
    agrupClasif = defaultdict(set)
    for datosEq in resultInicial:
        abrev = datosEq.abrevAusar
        kClasif = funcKey(datosEq, datosLR)
        agrupClasif[kClasif].add(abrev)

    for k in sorted(agrupClasif, reverse=True):
        abrevK = agrupClasif[k]
        if len(abrevK) == 1:
            for abrev in abrevK:
                resultFinal.append(datosLR[abrev])
        else:
            desempate = calculaClasifLiga(dataTemp=dataTemp, fecha=fecha, abrevList=abrevK, parcial=True,
                                          datosLR=datosLR)
            for sc in desempate:
                resultFinal.append(datosLR[sc.abrevAusar])

    result = resultFinal
    return result


def cmp(a, b):
    """
    Compares two values that can be compared (< and > must work)
    :param a:
    :param b:
    :return: 1 if a is bigger thanb, 0 if they are equal, -1 if b is bigger than a

    From https://docs.python.org/3.0/whatsnew/3.0.html#ordering-comparisons
    """

    return bool(a > b) - bool(a < b)


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

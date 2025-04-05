from collections import defaultdict
from operator import itemgetter
from typing import Tuple, List

from reportlab.lib.units import mm
from reportlab.platypus import NextPageTemplate, PageBreak, Spacer

from SMACB.Constants import infoSigPartido, LocalVisitante, OtherLoc
from SMACB.Programa.Clasif import entradaClas2kEmpatePareja, infoClasifComplPareja, calculaClasifLiga
from SMACB.Programa.Funciones import preparaListaTablas
from SMACB.Programa.Globals import CATESTADSEQASCENDING, recuperaClasifLiga, clasifLiga2dict
from SMACB.Programa.Secciones import tablaAnalisisEstadisticos, paginasJugadores, tablaLiga, auxGeneraLeyendaLiga, \
    cabeceraPortada, metadataPrograma, bloqueRestoJYBasics, tablaClasifLiga, reportTrayectoriaEquipos
from SMACB.TemporadaACB import TemporadaACB


def paginaEstadsEquipos(tempData: TemporadaACB, datosSig: infoSigPartido):
    result = []

    result.append(NextPageTemplate('normal'))
    result.append(PageBreak())
    reqData = {
        'Eq': ['P', 'Prec', 'POS', 'OER', 'DER', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-C', 'TC-I', 'TC%',
               'T1-C', 'T1-I', 'T1%', 'eff-t1', 'eff-t2', 'eff-t3', 't3/tc-I', 't3/tc-C', 'ppTC', 'PTC/PTCPot', 'R-D',
               'R-O', 'REB-T', 'EffRebD', 'EffRebO', 'A', 'A/BP', 'A/TC-C', 'BP', 'PNR', 'BR', 'TAP-F', 'TAP-C', 'FP-F',
               'FP-C'],
        'Rival': ['POS', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-C', 'TC-I', 'TC%', 'T1-C', 'T1-I', 'T1%',
                  'eff-t1', 'eff-t2', 'eff-t3', 't3/tc-I', 't3/tc-C', 'ppTC', 'PTC/PTCPot', 'R-D', 'R-O', 'REB-T', 'A',
                  'A/BP', 'A/TC-C', 'BP', 'PNR', 'BR', 'TAP-F', 'TAP-C', 'FP-F', 'FP-C']}
    result.append(
        tablaAnalisisEstadisticos(tempData, datosSig, magns2incl=reqData, magnsCrecientes=CATESTADSEQASCENDING))

    return result


def paginaJugadores(tempData: TemporadaACB, datosSig: infoSigPartido, argListaTablas: str):
    result = []

    tablasAmostrar = preparaListaTablas(argListaTablas)
    if tablasAmostrar:
        if len(datosSig.jugLocal) + len(datosSig.jugVis):
            infoJugadores = paginasJugadores(tempData, datosSig.abrevLV, datosSig.jugLocal, datosSig.jugVis,
                                             tablasAmostrar)
            result.extend(infoJugadores)

    return result


def paginaPartidosLiga(tempData: TemporadaACB, datosSig: infoSigPartido):
    result = []
    result.append(NextPageTemplate('apaisada'))
    result.append(PageBreak())
    result.append(tablaLiga(tempData, equiposAmarcar=datosSig.abrevLV, currJornada=int(datosSig.sigPartido['jornada'])))
    result.append(auxGeneraLeyendaLiga())

    return result


def paginaPortada(tempData: TemporadaACB, datosSig: infoSigPartido):
    result = []

    result.append(cabeceraPortada(tempData, datosSig))
    result.append(Spacer(width=120 * mm, height=1 * mm))
    result.append(metadataPrograma(tempData))
    result.append(Spacer(width=120 * mm, height=2 * mm))
    tabEstadsBasicas = bloqueRestoJYBasics(tempData, datosSig)
    result.append(tabEstadsBasicas)
    result.append(Spacer(width=120 * mm, height=2 * mm))
    tabClasif = tablaClasifLiga(tempData, datosSig)
    result.append(tabClasif)
    result.append(Spacer(width=120 * mm, height=2 * mm))
    trayectoria = reportTrayectoriaEquipos(tempData, datosSig)
    if trayectoria:
        result.append(trayectoria)
        result.append(Spacer(width=120 * mm, height=1 * mm))

    return result


def paginaCruces(tempData: TemporadaACB):
    recuperaClasifLiga(tempData=tempData)
    datosLR = clasifLiga2dict(tempData=tempData)

    acumulador = defaultdict(lambda: {'pendientes': 2})

    for p in tempData.Partidos.values():
        if tempData.Calendario.Jornadas[p.jornada]['esPlayoff']:
            continue
        clave = tuple(sorted(p.CodigosCalendario.values()))
        datosPart = p.DatosSuministrados['equipos']
        for loc in LocalVisitante:
            datos = datosPart[loc]
            datosOtro = datosPart[OtherLoc(loc)]
            abrev = datos['abrev']
            diffP = datos['puntos'] - datosOtro['puntos']
            if datos['haGanado']:
                sufLoc = "L" if loc == "Local" else "V"
                acumulador[clave]['prec'] = (abrev, sufLoc, diffP)

        acumulador[clave]['pendientes'] -= 1
        if acumulador[clave]['pendientes'] == 0:
            acumulador[clave]['prec'] = None

            l1 = calculaClasifLiga(tempData, abrevList=list(clave))
            sortkeys = sorted([(infoClas.abrevAusar, entradaClas2kEmpatePareja(infoClas, datosLR)) for infoClas in l1],
                              key=itemgetter(1), reverse=True)
            acumulador[clave]['ganador'] = infoGanadorEmparej(sortkeys)

    return acumulador


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

from reportlab.lib.units import mm
from reportlab.platypus import NextPageTemplate, PageBreak, Spacer

from SMACB.Constants import infoSigPartido
from SMACB.Programa.Funciones import preparaListaTablas
from SMACB.Programa.Globals import CATESTADSEQASCENDING
from SMACB.Programa.Presentacion import vuelcaCadena
from SMACB.Programa.Secciones import (tablaAnalisisEstadisticos, paginasJugadores, cabeceraPortada, metadataPrograma,
                                      bloqueRestoJYBasics, tablaClasifLiga, reportTrayectoriaEquipos, tablaCruces,
                                      tablaPartidosLigaReg)
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
    trayectoria, mensajeAviso = reportTrayectoriaEquipos(tempData, datosSig, limitRows=40)
    if trayectoria:
        result.append(trayectoria)
        if mensajeAviso != "":
            result.append(vuelcaCadena(mensajeAviso, fontsize=8))

        result.append(Spacer(width=120 * mm, height=1 * mm))

    return result


def paginaCruces(tempData: TemporadaACB):
    result = []
    result.append(NextPageTemplate('apaisada'))
    result.append(PageBreak())
    result.extend(tablaCruces(tempData, FONTSIZE=8.5))

    return result


def paginaPartidosLiga(tempData: TemporadaACB, datosSig: infoSigPartido):
    result = []
    result.append(NextPageTemplate('apaisada'))
    result.append(PageBreak())
    result.extend(
        tablaPartidosLigaReg(tempData, equiposAmarcar=datosSig.abrevLV, datosJornada=datosSig.sigPartido['infoJornada'],
                             FONTSIZE=8.5))

    return result

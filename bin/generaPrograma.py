from collections import defaultdict
from copy import copy

import reportlab.lib.colors as colors
import sys
from configargparse import ArgumentParser
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Table, SimpleDocTemplate, Paragraph, TableStyle, Spacer, NextPageTemplate, PageTemplate, \
    Frame, PageBreak
from time import strftime

from SMACB.CalendarioACB import NEVER
from SMACB.PartidoACB import LocalVisitante, OtherTeam
from SMACB.TemporadaACB import TemporadaACB, extraeCampoYorden
from Utils.FechaHora import Time2Str

estadGlobales = None
ESTADISTICO = 0  # 0 media, 1 mediana, 2 stdev, 3 max, 4 min

ESTILOS = getSampleStyleSheet()


def auxCalculaBalanceStr(record):
    victorias = record.get('V', 0)
    derrotas = record.get('D', 0)
    texto = f"{victorias}-{derrotas}"

    return texto


def cabeceraPortada(partido, tempData):
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = Time2Str(partido['fecha'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - J: <b>{j}</b><br/>{fh}</para>",
        style)

    cabLocal = datosCabEquipo(datosLocal, tempData, partido['fecha'])
    cabVisit = datosCabEquipo(datosVisit, tempData, partido['fecha'])

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def datosCabEquipo(datosEq, tempData, fecha):
    # TODO: Imagen
    nombre = datosEq['nombcorto']

    if tempData:
        clasifAux = tempData.clasifEquipo(datosEq['abrev'], fecha)
        clasifStr = auxCalculaBalanceStr(clasifAux)

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def datosEstadsEquipoPortada(tempData: TemporadaACB, eq: str):
    global estadGlobales
    if estadGlobales is None:
        estadGlobales = tempData.estadsLiga()

    targAbrev = list(tempData.Calendario.abrevsEquipo(eq).intersection(estadGlobales.keys()))[0]

    pFav, pFavOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'P', ESTADISTICO)
    pCon, pConOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'Priv', ESTADISTICO, False)

    pos, posOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'POS', ESTADISTICO)
    OER, OEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OER', ESTADISTICO)
    OERpot, OERpotOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OERpot', ESTADISTICO)
    DER, DEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'OER', ESTADISTICO, False)

    T2C, T2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-C', ESTADISTICO)
    T2I, T2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-I', ESTADISTICO)
    T2pc, T2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2%', ESTADISTICO)
    T3C, T3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-C', ESTADISTICO)
    T3I, T3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-I', ESTADISTICO)
    T3pc, T3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3%', ESTADISTICO)
    TCC, TCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-C', ESTADISTICO)
    TCI, TCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-I', ESTADISTICO)
    TCpc, TCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC%', ESTADISTICO)
    ppTC, ppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'ppTC', ESTADISTICO)
    ratT3, ratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 't3/tc-I', ESTADISTICO)
    Fcom, FcomOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'FP-F', ESTADISTICO, False)
    Frec, FrecOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'FP-F', ESTADISTICO, True)
    T1C, T1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-C', ESTADISTICO)
    T1I, T1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-I', ESTADISTICO)
    T1pc, T1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1%', ESTADISTICO)

    RebD, RebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-D', ESTADISTICO, True)
    RebO, RebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-O', ESTADISTICO, True)
    RebT, RebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'REB-T', ESTADISTICO, True)
    EffRebD, EffRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebD', ESTADISTICO, True)
    EffRebO, EffRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebO', ESTADISTICO, True)

    A, AOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A', ESTADISTICO, True)
    BP, BPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BP', ESTADISTICO, False)
    BR, BROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BR', ESTADISTICO, True)
    ApBP, ApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/BP', ESTADISTICO, True)
    ApTCC, ApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/TC-C', ESTADISTICO, True)

    ###

    rT2C, rT2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-C', ESTADISTICO)
    rT2I, rT2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-I', ESTADISTICO)
    rT2pc, rT2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2%', ESTADISTICO)
    rT3C, rT3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-C', ESTADISTICO)
    rT3I, rT3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-I', ESTADISTICO)
    rT3pc, rT3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3%', ESTADISTICO)
    rTCC, rTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-C', ESTADISTICO)
    rTCI, rTCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-I', ESTADISTICO)
    rTCpc, rTCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC%', ESTADISTICO)
    rppTC, rppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'ppTC', ESTADISTICO)
    rratT3, rratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 't3/tc-I', ESTADISTICO)
    rT1C, rT1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-C', ESTADISTICO)
    rT1I, rT1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-I', ESTADISTICO)
    rT1pc, rT1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1%', ESTADISTICO)

    rRebD, rRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-D', ESTADISTICO, True)
    rRebO, rRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-O', ESTADISTICO, True)
    rRebT, rRebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'REB-T', ESTADISTICO, True)

    rA, rAOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A', ESTADISTICO, True)
    rBP, rBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BP', ESTADISTICO, False)
    rBR, rBROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BR', ESTADISTICO, True)
    rApBP, rApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/BP', ESTADISTICO, True)
    rApTCC, rApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/TC-C', ESTADISTICO, True)

    ###

    resultEq = f"""
<b>PF</b>: {pFav:.2f}({pFavOrd}) <b>/</b> <b>PC</b>: {pCon:.2f}({pConOrd}) <b>/</b> 
<b>Pos</b>: {pos:.2f}({posOrd}) <b>/</b> <b>OER</b>: {OER:.2f}({OEROrd}) <b>/</b> <b>DER</b>: {DER:.2f}({DEROrd}) <b>/</b>
<b>T2</b>: {T2C:.2f}({T2IOrd})/{T2I:.2f}({T2IOrd}) {T2pc:.2f}%({T2pcOrd}) <b>/</b> <b>T3</b>: {T3C:.2f}({T3IOrd})/{T3I:.2f}({T3IOrd}) {T3pc:.2f}%({T3pcOrd}) <b>/</b>
<b>TC</b>: {TCC:.2f}({TCIOrd})/{TCI:.2f}({TCIOrd}) {TCpc:.2f}%({TCpcOrd}) <b>/</b> <b>P por TC-I</b>: {ppTC:.2f}({ppTCOrd}) % T3-I {ratT3:.2f}%({ratT3Ord}) <b>/</b>
<b>F com</b>: {Fcom:.2f}({FcomOrd})  <b>/</b> <b>F rec</b>: {Frec:.2f}({FrecOrd})  <b>/</b> <b>TL</b>: {T1C:.2f}({T1COrd})/{T1I:.2f}({T1IOrd}) {T1pc:.2f}%({T1pcOrd}) <b>/</b>
<b>Reb</b>: {RebD:.2f}({RebDOrd})+{RebO:.2f}({RebOOrd}) {RebT:.2f}({RebTOrd}) <b>/</b> <b>Eff D</b>: {EffRebD:.2f}({EffRebDOrd}) <b>Eff O</b>: {EffRebO:.2f}({EffRebOOrd}) <b>/</b>
<b>A</b>: {A:.2f}({AOrd}) <b>/</b> <b>BP</b>: {BP:.2f}({BPOrd}) <b>/</b> <b>BR</b>: {BR:.2f}({BROrd}) <b>/</b> <b>A/BP</b>: {ApBP:.2f}({ApBPOrd}) <b>/</b> <b>A/Can</b>: {ApTCC:.2f}({ApTCCOrd})<br/>

<B>RIVAL</B><br/>
<b>T2</b>: {rT2C:.2f}({rT2IOrd})/{rT2I:.2f}({rT2IOrd}) {rT2pc:.2f}%({rT2pcOrd}) <b>/</b> <b>T3</b>: {rT3C:.2f}({rT3IOrd})/{rT3I:.2f}({rT3IOrd}) {rT3pc:.2f}%({rT3pcOrd}) <b>/</b>
<b>TC</b>: {rTCC:.2f}({rTCIOrd})/{rTCI:.2f}({rTCIOrd}) {rTCpc:.2f}%({rTCpcOrd}) <b>/</b> <b>P por TC-I</b>: {rppTC:.2f}({rppTCOrd}) % T3-I {rratT3:.2f}%({rratT3Ord}) <b>/</b>
<b>TL</b>: {rT1C:.2f}({rT1COrd})/{rT1I:.2f}({rT1IOrd}) {rT1pc:.2f}%({rT1pcOrd}) <b>/</b> <b>Reb</b>: {rRebD:.2f}({rRebDOrd})+{rRebO:.2f}({rRebOOrd}) {rRebT:.2f}({rRebTOrd}) <b>/</b>
<b>A</b>: {rA:.2f}({rAOrd}) <b>/</b> <b>BP</b>: {rBP:.2f}({rBPOrd}) <b>/</b> <b>BR</b>: {rBR:.2f}({rBROrd}) <b>/</b> <b>A/BP</b>: {rApBP:.2f}({rApBPOrd}) <b>/</b> <b>A/Can</b>: {rApTCC:.2f}({rApTCCOrd})
"""

    return resultEq


def estadsEquipoPortada(tempData: TemporadaACB, abrevs: list):
    datLocal = datosEstadsEquipoPortada(tempData, abrevs[0])
    datVisitante = datosEstadsEquipoPortada(tempData, abrevs[1])

    style = ParagraphStyle('Normal', align='left', fontName='Helvetica', fontSize=10, leading=11, )

    parLocal = Paragraph(datLocal, style)
    parVisit = Paragraph(datVisitante, style)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[parLocal, parVisit]], colWidths=[100 * mm, 100 * mm], style=tStyle)

    return t


def datosTablaLiga(tempData: TemporadaACB):
    FONTSIZE = 10
    CELLPAD = 3 * mm

    estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                              alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
    ESTILOS.add(estCelda)

    # Precalcula el contenido de la tabla
    auxTabla = defaultdict(dict)
    for jId, jDatos in tempData.Calendario.Jornadas.items():
        for part in jDatos['partidos']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part
        for part in jDatos['pendientes']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part

    # En la clasificación está el contenido de los márgenes, de las diagonales y el orden de presentación
    # de los equipos
    clasif = tempData.clasifLiga()
    seqIDs = [(pos, list(clasif[pos]['idEq'])[0]) for pos in range(len(clasif))]

    datosTabla = []
    cabFila = [Paragraph('<b>Casa/Fuera</b>', style=estCelda)] + [
        Paragraph('<b>' + list(clasif[pos]['abrevsEq'])[0] + '</b>', style=estCelda) for pos, _ in seqIDs] + [
                  Paragraph('<b>Como local</b>', style=estCelda)]
    datosTabla.append(cabFila)
    for pos, idLocal in seqIDs:
        fila = []
        nombreCorto = sorted(clasif[pos]['nombresEq'], key=lambda n: len(n))[0]
        abrev = list(clasif[pos]['abrevsEq'])[0]
        fila.append(Paragraph(f"{nombreCorto} (<b>{abrev}</b>)", style=estCelda))
        for _, idVisit in seqIDs:
            if idLocal != idVisit:
                part = auxTabla[idLocal][idVisit]
                fecha = strftime("%d-%m", part['fecha']) if (('fecha' in part) and (part['fecha'] != NEVER)) else 'TBD'
                jornada = part['jornada']

                texto = f"J:{jornada}<br/>@{fecha}"
                if not part['pendiente']:
                    pURL = part['url']
                    pTempFecha = tempData.Partidos[pURL].FechaHora
                    fecha = strftime("%d-%m", pTempFecha)
                    pLocal = part['equipos']['Local']['puntos']
                    pVisit = part['equipos']['Visitante']['puntos']
                    texto = f"J:{jornada}<br/><b>{pLocal}-{pVisit}</b>"  #:@{fecha}
            else:
                auxTexto = auxCalculaBalanceStr(clasif[pos])
                texto=f"<b>{auxTexto}</b>"
            fila.append(Paragraph(texto, style=estCelda))

        fila.append(Paragraph(auxCalculaBalanceStr(clasif[pos]['CasaFuera']['Local']), style=estCelda))
        datosTabla.append(fila)

    filaBalFuera = [Paragraph('<b>Como visitante</b>', style=estCelda)]
    for pos, idLocal in seqIDs:
        filaBalFuera.append(Paragraph(auxCalculaBalanceStr(clasif[pos]['CasaFuera']['Visitante']), style=estCelda))
    filaBalFuera.append([])
    datosTabla.append(filaBalFuera)

    return datosTabla


def listaEquipos(tempData):
    print("Abreviatura -> nombre(s) equipo")
    for abr in sorted(tempData.Calendario.tradEquipos['c2n']):
        listaEquiposAux = sorted(tempData.Calendario.tradEquipos['c2n'][abr], key=lambda x: (len(x), x), reverse=True)
        listaEquiposStr = ",".join(listaEquiposAux)
        print(f'{abr}: {listaEquiposStr}')
    sys.exit(0)


def mezclaPartJugados(tempData, abrevs, partsIzda, partsDcha):
    partsIzdaAux = copy(partsIzda)
    partsDchaAux = copy(partsDcha)
    lineas = list()

    abrIzda, abrDcha = abrevs
    abrevsIzda = tempData.Calendario.abrevsEquipo(abrIzda)
    abrevsDcha = tempData.Calendario.abrevsEquipo(abrDcha)

    while (len(partsIzdaAux) > 0) or (len(partsDchaAux) > 0):
        bloque = dict()

        try:
            priPartIzda = partsIzdaAux[0]
        except IndexError:
            bloque['J'] = partsDchaAux[0].Jornada
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
            lineas.append(bloque)
            continue
        try:
            priPartDcha = partsDchaAux[0]
        except IndexError:
            bloque['J'] = priPartIzda.Jornada
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            lineas.append(bloque)
            continue

        bloque = dict()
        if priPartIzda.Jornada == priPartDcha.Jornada:
            bloque['J'] = priPartIzda.Jornada
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
        else:
            if (priPartIzda.FechaHora, priPartIzda.Jornada) < (priPartDcha.FechaHora, priPartDcha.Jornada):
                bloque['J'] = priPartIzda.Jornada
                bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            else:
                bloque['J'] = priPartDcha.Jornada
                bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)

        lineas.append(bloque)

    return lineas


def partidoTrayectoria(partido, abrevs, datosTemp):
    # Cadena de información del partido
    strFecha = strftime("%d-%m", partido.FechaHora)
    abrEq = list(abrevs.intersection(partido.DatosSuministrados['participantes']))[0]
    abrRival = list(partido.DatosSuministrados['participantes'].difference(abrevs))[0]
    locEq = partido.DatosSuministrados['abrev2loc'][abrEq]
    locRival = OtherTeam(locEq)
    prefLoc = "vs" if locEq == "Local" else "@"
    nomRival = partido.DatosSuministrados['equipos'][locRival]['nombcorto']
    clasifAux = datosTemp.clasifEquipo(abrRival, partido.FechaHora)
    clasifStr = auxCalculaBalanceStr(clasifAux)
    strRival = f"{strFecha}: {prefLoc} {nomRival} {clasifStr}"

    # Cadena del resultado del partido
    # TODO: Esto debería ir en HTML o Markup correspondiente
    prefV = {loc: ('<b>', '</b>') if partido.DatosSuministrados['equipos'][loc]['haGanado'] else ('', '') for loc in
             LocalVisitante}
    prefMe = {loc: ('<u>', '</u>') if (loc == locEq) else ('', '') for loc in LocalVisitante}
    resAux = [
        f"{prefV[loc][0]}{prefMe[loc][0]}{partido.DatosSuministrados['resultado'][loc]}{prefMe[loc][1]}{prefV[loc][1]}"
        for
        loc in LocalVisitante]
    strResultado = "-".join(resAux) + (" (V)" if partido.DatosSuministrados['equipos'][locEq]['haGanado'] else " (D)")

    return strRival, strResultado


def reportTrayectoria(listaTrayectoria):
    filas = []

    resultStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=12, align='center')
    cellStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=12)
    jornStyle = ParagraphStyle('trayStyle', fontName='Helvetica-Bold', fontSize=13, align='right')

    for f in listaTrayectoria:
        datosIzda = f.get('izda', ['', ''])
        datosDcha = f.get('dcha', ['', ''])
        jornada = f['J']

        aux = [Paragraph(f"<para align='center'>{datosIzda[1]}</para>"),
               Paragraph(f"<para>{datosIzda[0]}</para>"),
               Paragraph(f"<para align='center' fontName='Helvetica-Bold'>{str(jornada)}</para>"),
               Paragraph(f"<para>{datosDcha[0]}</para>"),
               Paragraph(f"<para align='center'>{datosDcha[1]}</para>")]
        filas.append(aux)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])

    t = Table(data=filas, style=tStyle, colWidths=[23 * mm, 72 * mm, 10 * mm, 72 * mm, 23 * mm])

    return t


def tablaLiga(tempData: TemporadaACB):
    CELLPAD = 0.3 * mm
    FONTSIZE = 10

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE), ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD),
                         ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD), ('TOPPADDING', (0, 0), (-1, -1), CELLPAD),
                         ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD), ])
    datosAux = datosTablaLiga(tempData)

    t = Table(datosAux, style=tStyle)

    return t


def preparaLibro(outfile, tempData, datosSig):
    MARGENFRAME = 2 * mm
    frameNormal = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[0] - 2 * MARGENFRAME, height=A4[1] - 2 * MARGENFRAME,
                        leftPadding=MARGENFRAME,
                        bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME, topPadding=MARGENFRAME)
    frameApaisado = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[1] - 2 * MARGENFRAME, height=A4[0] - 2 * MARGENFRAME,
                          leftPadding=MARGENFRAME,
                          bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME, topPadding=MARGENFRAME)
    pagNormal = PageTemplate('normal', pagesize=A4, frames=[frameNormal], autoNextPageTemplate='normal')
    pagApaisada = PageTemplate('apaisada', pagesize=landscape(A4), frames=[frameApaisado],
                               autoNextPageTemplate='apaisada')

    doc = SimpleDocTemplate(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=5 * mm,
                            leftMargin=5 * mm,
                            rightMargin=5 * mm,
                            topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    # pagNormal = PageTemplate('normal', frames=[frameApaisado], pagesize=A4, autoNextPageTemplate='normal')
    #
    # doc.addPageTemplates(pagNormal)
    # pagApaisada = PageTemplate('apaisada', frames=[frameNormal], pagesize=landscape(A4),
    #                            autoNextPageTemplate='apaisada')

    # doc.addPageTemplates(pagApaisada)

    # pdfFile = canvas.Canvas(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',                            initialLeading=0.5 * mm)
    story = []

    (sigPartido, abrEqs, juIzda, peEq, juDcha, peRiv, targLocal) = datosSig

    antecedentes = {p.url for p in juIzda}.intersection({p.url for p in juDcha})

    mezParts = mezclaPartJugados(tempData, abrEqs, juIzda, juDcha)

    story.append(cabeceraPortada(sigPartido, tempData))

    story.append(Spacer(width=120 * mm, height=2 * mm))
    story.append(estadsEquipoPortada(tempData, abrEqs))

    if antecedentes:
        print("Antecedentes!")
    else:
        story.append(Spacer(width=120 * mm, height=3 * mm))
        story.append(Paragraph("Sin antecedentes esta temporada"))

    if mezParts:
        story.append(Spacer(width=120 * mm, height=3 * mm))
        trayectoria = reportTrayectoria(mezParts)
        story.append(trayectoria)

    story.append(NextPageTemplate('apaisada'))
    story.append(PageBreak())
    story.append(tablaLiga(tempData))

    #   story.append(NextPageTemplate('apaisada'))

    doc.build(story)


def parse_arguments():
    descriptionTXT = "Prepares a booklet for the next game of a team"

    parser = ArgumentParser(description=descriptionTXT)
    parser.add_argument("-t", "--acbfile", dest="acbfile", action="store", required=True, env_var="ACB_FILE",
                        help="Nombre del ficheros de temporada", )
    parser.add_argument("-l", "--listaequipos", dest='listaEquipos', action="store_true", required=False,
                        help="Lista siglas para equipos", )

    parser.add_argument("-e", "--equipo", dest="equipo", action="store", required=False,
                        help="Abreviatura del equipo deseado (usar -l para obtener lista)", )
    parser.add_argument("-o", "--outfile", dest="outfile", action="store", help="Fichero PDF generado",
                        required=False, )

    parser.add_argument("-c", "--cachedir", dest="cachedir", action="store", required=False, env_var="ACB_CACHEDIR",
                        help="Ubicación de caché de ficheros", )

    result = parser.parse_args()

    return result


def main(args):
    tempData = cargaTemporada(args.acbfile)

    if args.listaEquipos:
        listaEquipos(tempData)

    REQARGS = ['equipo', 'outfile']
    missingReqs = {k for k in REQARGS if (k not in args) or (args.__getattribute__(k) is None)}
    if missingReqs:
        missingReqsStr = ",".join(sorted(missingReqs))
        print(f"Faltan argumentos (ver -h): {missingReqsStr}")
        sys.exit(1)
    try:
        datosSig = tempData.sigPartido(args.equipo)
    except KeyError as exc:
        print(f"Equipo desconocido '{args.equipo}': {exc}")
        sys.exit(1)

    preparaLibro(args.outfile, tempData, datosSig)


if __name__ == '__main__':
    args = parse_arguments()
    main(args)

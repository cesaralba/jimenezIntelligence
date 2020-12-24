from collections import defaultdict
from copy import copy

import reportlab.lib.colors as colors
import sys
from configargparse import ArgumentParser
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Table, SimpleDocTemplate, Paragraph, TableStyle, Spacer
from time import strftime

from SMACB.CalendarioACB import NEVER
from SMACB.PartidoACB import LocalVisitante, OtherTeam
from SMACB.TemporadaACB import TemporadaACB, extraeCampoYorden
from Utils.FechaHora import Time2Str

estadGlobales = None
ESTAD = 0  # 0 media, 1 mediana, 2 stdev, 3 max, 4 min


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
        clasifStr = "(%i-%i)" % (clasifAux.get('V', 0), clasifAux.get('D', 0))

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'>{nombre}</para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def datosEstadsEquipoPortada(tempData: TemporadaACB, eq: str):
    global estadGlobales
    if estadGlobales is None:
        estadGlobales = tempData.estadsLiga()

    targAbrev = list(tempData.Calendario.abrevsEquipo(eq).intersection(estadGlobales.keys()))[0]

    pFav, pFavOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'P', ESTAD)
    pCon, pConOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'Priv', ESTAD, False)

    pos, posOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'POS', ESTAD)
    OER, OEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OER', ESTAD)
    OERpot, OERpotOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OERpot', ESTAD)
    DER, DEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'OER', ESTAD, False)

    T2C, T2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-C', ESTAD)
    T2I, T2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-I', ESTAD)
    T2pc, T2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2%', ESTAD)
    T3C, T3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-C', ESTAD)
    T3I, T3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-I', ESTAD)
    T3pc, T3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3%', ESTAD)
    TCC, TCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-C', ESTAD)
    TCI, TCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-I', ESTAD)
    TCpc, TCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC%', ESTAD)
    ppTC, ppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'ppTC', ESTAD)
    ratT3, ratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 't3/tc-I', ESTAD)
    Fcom, FcomOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'FP-F', ESTAD, False)
    Frec, FrecOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'FP-F', ESTAD, True)
    T1C, T1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-C', ESTAD)
    T1I, T1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-I', ESTAD)
    T1pc, T1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1%', ESTAD)

    RebD, RebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-D', ESTAD, True)
    RebO, RebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-O', ESTAD, True)
    RebT, RebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'REB-T', ESTAD, True)
    EffRebD, EffRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebD', ESTAD, True)
    EffRebO, EffRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebO', ESTAD, True)

    A, AOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A', ESTAD, True)
    BP, BPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BP', ESTAD, False)
    BR, BROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BR', ESTAD, True)
    ApBP, ApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/BP', ESTAD, True)
    ApTCC, ApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/TC-C', ESTAD, True)

    ###

    rT2C, rT2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-C', ESTAD)
    rT2I, rT2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-I', ESTAD)
    rT2pc, rT2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2%', ESTAD)
    rT3C, rT3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-C', ESTAD)
    rT3I, rT3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-I', ESTAD)
    rT3pc, rT3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3%', ESTAD)
    rTCC, rTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-C', ESTAD)
    rTCI, rTCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-I', ESTAD)
    rTCpc, rTCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC%', ESTAD)
    rppTC, rppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'ppTC', ESTAD)
    rratT3, rratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 't3/tc-I', ESTAD)
    rT1C, rT1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-C', ESTAD)
    rT1I, rT1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-I', ESTAD)
    rT1pc, rT1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1%', ESTAD)

    rRebD, rRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-D', ESTAD, True)
    rRebO, rRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-O', ESTAD, True)
    rRebT, rRebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'REB-T', ESTAD, True)

    rA, rAOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A', ESTAD, True)
    rBP, rBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BP', ESTAD, False)
    rBR, rBROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BR', ESTAD, True)
    rApBP, rApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/BP', ESTAD, True)
    rApTCC, rApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/TC-C', ESTAD, True)

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
    auxTabla = defaultdict(dict)
    datosTabla = []
    for jId, jDatos in tempData.Calendario.Jornadas.items():
        for part in jDatos['partidos']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part
        for part in jDatos['pendientes']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part

    clasif = tempData.clasifLiga()
    seqIDs = [(pos, list(clasif[pos]['idEq'])[0]) for pos in range(len(clasif))]

    cabFila = ['Casa/Fuera'] + [list(clasif[pos]['abrevsEq'])[0] for pos, _ in seqIDs] + ['Bal Local']
    datosTabla.append(cabFila)
    for pos, idLocal in seqIDs:
        fila = []
        nombreCorto = sorted(clasif[pos]['nombresEq'], key=lambda n: len(n))[0]
        abrev = list(clasif[pos]['abrevsEq'])[0]
        fila.append(f"{nombreCorto} ({abrev})")
        for _, idVisit in seqIDs:
            if idLocal != idVisit:
                part = auxTabla[idLocal][idVisit]
                fecha = strftime("%d-%m", part['fecha']) if (('fecha' in part) and (part['fecha'] != NEVER)) else 'TBD'
                jornada = part['jornada']

                print("CAP", fecha, part['fecha'])
                texto = f"J:{jornada} {fecha}"
                if not part['pendiente']:
                    pURL = part['url']
                    pTempFecha = tempData.Partidos[pURL].FechaHora
                    fecha = strftime("%d-%m", pTempFecha)
                    pLocal = part['equipos']['Local']['puntos']
                    pVisit = part['equipos']['Visitante']['puntos']
                    texto = f"J:{jornada} {fecha}<br/><b>{pLocal}-{pVisit}</b>"
            else:
                victorias = clasif[pos].get('V', 0)
                derrotas = clasif[pos].get('D', 0)
                texto = f"{victorias} - {derrotas}"
            fila.append(texto)

        victorias = clasif[pos]['CasaFuera']['Local'].get('V', 0)
        derrotas = clasif[pos]['CasaFuera']['Local'].get('D', 0)
        texto = f"{victorias} - {derrotas}"
        fila.append(texto)
        datosTabla.append(fila)

    filaBalFuera = ['Bal Visit']
    for pos, idLocal in seqIDs:
        victorias = clasif[pos]['CasaFuera']['Visitante'].get('V', 0)
        derrotas = clasif[pos]['CasaFuera']['Visitante'].get('D', 0)
        texto = f"{victorias} - {derrotas}"
        filaBalFuera.append(texto)
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
    clasifStr = "(%i-%i)" % (clasifAux.get('V', 0), clasifAux.get('D', 0))
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


def preparaLibro(outfile, tempData, datosSig):
    doc = SimpleDocTemplate(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=5 * mm,
                            leftMargin=5 * mm,
                            rightMargin=5 * mm,
                            topMargin=5 * mm,
                            bottomMargin=5 * mm)
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

    doc.build(story)

    # print(sigPartido)
    # print("-------")
    # print(targLocal)
    # print("-------")
    # print(juIzda)
    # print("-------")
    # print(juDcha)
    # print("-------")


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

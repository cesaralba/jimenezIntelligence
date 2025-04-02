from itertools import product
from time import strftime, gmtime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, TableStyle, Table, NextPageTemplate, PageBreak, Spacer

import SMACB.Programa.Globals
from SMACB.Constants import infoSigPartido, MARCADORESCLASIF, filaTrayectoriaEq
from SMACB.Programa.Constantes import estiloNegBal, estiloPosMarker, colEq
from SMACB.Programa.Datos import datosTablaClasif, datosJugadores, auxFindTargetAbrevs, datosAnalisisEstadisticos
from SMACB.Programa.FuncionesAux import auxCalculaFirstBalNeg, partidoTrayectoria, auxBold
from SMACB.Programa.Globals import recuperaClasifLiga, recuperaEstadsGlobales
from SMACB.Programa.Presentacion import tablaEstadsBasicas, tablaRestoJornada, bloqueCabEquipo, datosTablaLiga, \
    auxTablaLigaListaEstilos, tablasJugadoresEquipo, auxGeneraLeyendaEstadsCelda, auxFilasTablaEstadisticos
from SMACB.TemporadaACB import TemporadaACB
from Utils.FechaHora import time2Str

allMagnsInEstads = SMACB.Programa.Globals.allMagnsInEstads


def cabeceraPortada(tempData: TemporadaACB, datosSig: infoSigPartido):
    partido = datosSig.sigPartido
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = time2Str(partido['fechaPartido'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - "
        f"J: " f"<b>{j}</b><br/>{fh}</para>", style)

    cabLocal = bloqueCabEquipo(datosLocal, tempData, partido['fechaPartido'], currJornada=int(j))
    cabVisit = bloqueCabEquipo(datosVisit, tempData, partido['fechaPartido'], currJornada=int(j))

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def metadataPrograma(tempData: TemporadaACB):
    FONTSIZE = 6

    FORMATOfecha = "%Y-%m-%d %H:%M (%z)"
    fechaGen = strftime(FORMATOfecha, gmtime())
    tempDesc = strftime(FORMATOfecha, tempData.timestamp)
    mensaje = (f"Datos procedentes de https://www.acb.com y elaboración propia. Generado en {fechaGen}. Datos "
               f"descargados en {tempDesc}")

    metadataStyle = ParagraphStyle('tabEstadsRowHeader', fontSize=FONTSIZE, alignment=TA_LEFT, leading=1)

    result = Paragraph(mensaje, style=metadataStyle)

    return result


def bloqueRestoJYBasics(tempData: TemporadaACB, datosSig: infoSigPartido):
    tabEBasics = tablaEstadsBasicas(tempData, datosSig)
    tabRestoJ = tablaRestoJornada(tempData, datosSig)

    tStyle = TableStyle(
        [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEADING', (0, 0), (-1, -1), 0), ('LEFTPADDING', (0, 0), (-1, -1), 3),
         ('RIGHTPADDING', (0, 0), (-1, -1), 3),

         ])

    datosTabla = [[tabRestoJ, tabEBasics]]
    anchoCols = [118 * mm, 77 * mm]

    t = Table(data=datosTabla, colWidths=anchoCols, style=tStyle)

    return t


def tablaClasifLiga(tempData: TemporadaACB, datosSig: infoSigPartido):
    FONTPARA = 8.5
    FONTSIZE = 8

    def preparaFila(dato):
        result = [Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.posic}</para>"),
                  Paragraph(f"<para align='left' fontsize={FONTPARA}>{dato.nombre}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.jugs}</para>"),
                  Paragraph(f"<para align='center' fontsize={FONTPARA}>{dato.victs:2}-{dato.derrs:2}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.ratio:3.0f}%</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.puntF:4}/{dato.puntC:4}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.diffP}</para>")]
        return result

    recuperaClasifLiga(tempData)
    filasClasLiga = datosTablaClasif(tempData, datosSig)
    posFirstNegBal = auxCalculaFirstBalNeg(SMACB.Programa.Globals.clasifLiga)
    filasAresaltar = []
    filaCab = [Paragraph("<para align='center'><b>#</b></para>"),
               Paragraph("<para align='center'><b>Equipo</b></para>"),
               Paragraph("<para align='center'><b>J</b></para>"), Paragraph("<para align='center'><b>V-D</b></para>"),
               Paragraph("<para align='center'><b>%</b></para>"),
               Paragraph("<para align='center'><b>PF / PC </b></para>"),
               Paragraph("<para align='center'><b>Df</b></para>")]

    lStyle = [('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE * 0.8),
              ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
              ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1)]

    listasClas = [[filaCab], [filaCab]]
    listasStyles = [TableStyle(lStyle), TableStyle(lStyle)]

    # Crea las listas para las subtablas
    for posic, datosFila in enumerate(filasClasLiga):
        t, e = posic // SMACB.Programa.Globals.mitadEqs, posic % SMACB.Programa.Globals.mitadEqs

        listasClas[t].append(preparaFila(datosFila))
        if datosFila.resalta:
            filasAresaltar.append((t, e))

    ANCHOMARCAPOS = 2
    for pos in MARCADORESCLASIF:
        commH = "LINEBELOW"
        incr = 0 if pos >= 0 else -1
        t = 0 if pos >= 0 else 1
        estilo = estiloNegBal if (posFirstNegBal is not None) and ((posFirstNegBal - 1) == pos) else estiloPosMarker
        listasStyles[t].add(commH, (0, pos + incr), (-1, pos + incr), ANCHOMARCAPOS, *estilo)

    # Balance negativo
    if (posFirstNegBal is not None) and ((posFirstNegBal - 1) not in MARCADORESCLASIF):
        t, e = (posFirstNegBal - 1) // SMACB.Programa.Globals.mitadEqs, (posFirstNegBal - 1) % SMACB.Programa.Globals.mitadEqs
        listasStyles[t].add("LINEBELOW", (0, e), (-1, e), ANCHOMARCAPOS, *estiloNegBal)

    # Marca equipos del programa
    if filasAresaltar:
        for t, e in filasAresaltar:
            listasStyles[t].add("BACKGROUND", (0, e + 1), (-1, e + 1), colEq)

    ANCHOPOS = 21.5
    ANCHOEQUIPO = 92
    ANCHOPARTS = 23.7
    ANCHOPERC = 30
    ANCHOPUNTS = 54.5
    ANCHODIFF = 29.5
    listaAnchos = [ANCHOPOS, ANCHOEQUIPO, ANCHOPARTS, ANCHOPARTS * 1.4, ANCHOPERC, ANCHOPUNTS, ANCHODIFF]

    listaTablas = [Table(data=listasClas[t], style=listasStyles[t], colWidths=listaAnchos, rowHeights=FONTSIZE + 4) for
                   t in range(2)]

    result = Table(data=[listaTablas])
    return result


def reportTrayectoriaEquipos(tempData: TemporadaACB, infoPartido: infoSigPartido):
    sigPartido = infoPartido.sigPartido

    FONTSIZE = 8

    filasPrecedentes = set()
    incrFila = 0
    marcaCurrJornada = None
    mergeIzdaList = []
    mergeDchaList = []

    j17izda = None
    j17dcha = None

    trayectoriasCombinadas = tempData.mergeTrayectoriaEquipos(*(tuple(infoPartido.abrevLV)), True, True)

    filasTabla = []

    resultStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE, alignment=TA_CENTER)
    cellStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE, alignment=TA_LEFT)
    jornStyle = ParagraphStyle('trayStyle', fontName='Helvetica-Bold', fontSize=FONTSIZE + 1, alignment=TA_CENTER)

    def preparaCeldasTrayectoria(data: filaTrayectoriaEq | None, ladoIzdo: bool = False) -> (list, bool):
        merge = False
        if data is None:
            result = [None, None]
            merge = True
        elif data.pendiente:
            etiq, _ = partidoTrayectoria(data, tempData)
            result = [Paragraph(etiq, style=cellStyle), None]
            merge = True
        else:
            etiq, marcador = partidoTrayectoria(data, tempData)
            result = [Paragraph(etiq, style=cellStyle), Paragraph(marcador, style=resultStyle)]
            if ladoIzdo:
                result.reverse()

        return result, merge

    for numFila, fila in enumerate(trayectoriasCombinadas):
        datosIzda = fila.izda
        datosDcha = fila.dcha
        jornada = fila.jornada

        if fila.precedente:
            if fila.jornada == sigPartido['jornada']:
                marcaCurrJornada = numFila
                incrFila = -1
                continue
            filasPrecedentes.add(numFila + incrFila)

        if fila.jornada == '17':
            if datosIzda and datosIzda.pendiente:
                j17izda = numFila + incrFila
            if datosDcha and datosDcha.pendiente:
                j17dcha = numFila + incrFila

        celdasIzda, mergeIzda = preparaCeldasTrayectoria(datosIzda, True)
        celdasDcha, mergeDcha = preparaCeldasTrayectoria(datosDcha, False)

        if mergeIzda:
            mergeIzdaList.append(numFila + incrFila)
        if mergeDcha:
            mergeDchaList.append(numFila + incrFila)

        celdaJornada = [Paragraph(f"{str(jornada)}", style=jornStyle)]
        aux = celdasIzda + celdaJornada + celdasDcha
        filasTabla.append(aux)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1), ])

    # Formatos extra a la tabla
    if marcaCurrJornada:
        tStyle.add("LINEABOVE", (0, marcaCurrJornada), (-1, marcaCurrJornada), 1 * mm, colors.black)

    if j17izda:
        tStyle.add("LINEBELOW", (0, j17izda), (2, j17izda), 0.75 * mm, colors.black, "squared", (1, 8))
    if j17dcha:
        tStyle.add("LINEBELOW", (-3, j17dcha), (-1, j17dcha), 0.75 * mm, colors.black, "squared", (1, 8))

    for fNum in filasPrecedentes:
        tStyle.add("BACKGROUND", (0, fNum), (-1, fNum), colors.lightgrey)

    for fNum in mergeIzdaList:
        tStyle.add("SPAN", (0, fNum), (1, fNum))
    for fNum in mergeDchaList:
        tStyle.add("SPAN", (-2, fNum), (-1, fNum))

    ANCHORESULTADO = (FONTSIZE * 0.6) * 13
    ANCHOETPARTIDO = (FONTSIZE * 0.6) * 35
    ANCHOJORNADA = ((FONTSIZE + 1) * 0.6) * 5

    ANCHOCOLS = [ANCHORESULTADO, ANCHOETPARTIDO, ANCHOJORNADA, ANCHOETPARTIDO, ANCHORESULTADO]

    t = Table(data=filasTabla, style=tStyle, colWidths=ANCHOCOLS, rowHeights=FONTSIZE + 4.5)

    return t


def tablaLiga(tempData: TemporadaACB, equiposAmarcar=None, currJornada: int = None):
    CELLPAD = 0.3 * mm
    FONTSIZE = 9

    datosAux, coordsJuPe, firstNegBal = datosTablaLiga(tempData, currJornada)

    alturas = [22] + [28.7] * (len(datosAux) - 2) + [21]
    anchos = [76] + [39] * (len(datosAux) - 2) + [38]

    listaEstilos = auxTablaLigaListaEstilos(CELLPAD, FONTSIZE, coordsJuPe, datosAux, equiposAmarcar, firstNegBal)
    tStyle = TableStyle(listaEstilos)

    t = Table(datosAux, style=tStyle, rowHeights=alturas, colWidths=anchos)

    return t


def auxGeneraLeyendaLiga():
    texto = ("<b>Leyenda en balance total</b>: <b>A</b>:&nbsp;Partido(s) adelantado(s)<b> J</b>:&nbsp;Jornada actual "
             "pendiente de jugar<b> "
             "P</b>:&nbsp;Partido(s) pendiente(s)")

    FONTSIZE = 8
    legendStyle = ParagraphStyle('tabLigaLegend', fontSize=FONTSIZE, alignment=TA_JUSTIFY, wordWrap=True,
                                 leading=FONTSIZE + 0.5, )
    result = Paragraph(texto, style=legendStyle)

    return result


def paginasJugadores(tempData: TemporadaACB, abrEqs, juLocal, juVisit, tablas: List[str]):
    result = []

    if not tablas:
        return result

    if len(juLocal):
        datosLocal = datosJugadores(tempData, abrEqs[0], juLocal)
        tablasJugadLocal = tablasJugadoresEquipo(datosLocal, abrev=abrEqs[0], tablasIncluidas=tablas)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (_, t) in tablasJugadLocal:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(t)
            result.append(NextPageTemplate('apaisada'))

    if len(juVisit):
        datosVisit = datosJugadores(tempData, abrEqs[1], juVisit)
        tablasJugadVisit = tablasJugadoresEquipo(datosVisit, abrev=abrEqs[1], tablasIncluidas=tablas)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (_, t) in tablasJugadVisit:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(NextPageTemplate('apaisada'))
            result.append(t)

    return result

############## tablaAnalisisEstadisticos



def tablaAnalisisEstadisticos(tempData: TemporadaACB, datosSig: infoSigPartido, magns2incl: list | set | None = None,
                              magnsCrecientes: list | set | None = None
                              ) -> Table:
    catsAscending = {} if magnsCrecientes is None else set(magnsCrecientes)

    recuperaEstadsGlobales(tempData)
    targetAbrevs = auxFindTargetAbrevs(tempData, datosSig)

    clavesEq, clavesRiv = allMagnsInEstads, allMagnsInEstads
    if isinstance(magns2incl, list):
        clavesEq = list(magns2incl)
        clavesRiv = clavesEq
    elif isinstance(magns2incl, dict):
        clavesEq = magns2incl.get('Eq', {})
        clavesRiv = magns2incl.get('Rival', {})
    claves2wrk = list(product(['Eq'], clavesEq)) + list(product(['Rival'], clavesRiv))
    if len(claves2wrk) == 0:
        raise ValueError(f"tablaAnalisisEstadisticos: No hay valores para incluir en la tabla: parametro {magns2incl}")

    datos, abrevs2leyenda = datosAnalisisEstadisticos(tempData, datosSig, magnsAscending=catsAscending,
                                                      magn2include=claves2wrk)

    FONTSIZE = 8

    headerStyle = ParagraphStyle('tabEstadsHeader', fontSize=FONTSIZE + 2, alignment=TA_CENTER, leading=12)
    rowHeaderStyle = ParagraphStyle('tabEstadsRowHeader', fontSize=FONTSIZE, alignment=TA_LEFT, leading=10)
    cellStyle = ParagraphStyle('tabEstadsCell', fontSize=FONTSIZE, alignment=TA_RIGHT, leading=10)

    ANCHOEQL = 14.2
    ANCHOLABEL = 68.4
    ANCHOEQUIPO = 55.5
    ANCHOMAXMIN = 68.9
    ANCHOLIGA = 65.2
    ANCHOLEYENDA = 170

    LISTAANCHOS = [ANCHOEQL, ANCHOLABEL, ANCHOEQUIPO, ANCHOEQUIPO, ANCHOMAXMIN, ANCHOLIGA, ANCHOMAXMIN]

    filaCab = [None, Paragraph(auxBold("Estad"), style=headerStyle),
               Paragraph(auxBold(f"{targetAbrevs['Local']}"), style=headerStyle),
               Paragraph(auxBold(f"{targetAbrevs['Visitante']}"), style=headerStyle),
               Paragraph(auxBold("Mejor"), style=headerStyle), Paragraph(auxBold("ACB"), style=headerStyle),
               Paragraph(auxBold("Peor"), style=headerStyle)]

    filasTabla, leyendas = auxFilasTablaEstadisticos(datos, clavesEquipo=clavesEq, clavesRival=clavesRiv,
                                                     estiloCabCelda=rowHeaderStyle, estiloCelda=cellStyle)

    EXTRALEYENDA = 0
    ESTILOLEYENDA = []
    if leyendas:
        LISTAANCHOS.append(ANCHOLEYENDA)
        filaCab.append(Paragraph(auxBold("Leyenda"), style=headerStyle))
        EXTRALEYENDA = -1
        ESTILOLEYENDA = [('SPAN', (-1, 1), (-1, -1)), ('VALIGN', (-1, 1), (-1, -1), 'TOP')]

        filasTabla[0][-1] = auxGeneraLeyendaEstadsCelda(leyendas, FONTSIZE,
                                                        abrevs2leyenda.union(set(targetAbrevs.values())))

    listaEstilos = [('BOX', (1, 1), (-1 + EXTRALEYENDA, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (1, 1), (-1 + EXTRALEYENDA, -1), 0.5, colors.black), ('SPAN', (0, 1), (0, len(clavesEq))),
                    ('SPAN', (0, len(clavesEq)), (0, -1)),
                    ('BOX', (1, 1), (-1 + EXTRALEYENDA, len(clavesEq)), 2, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('BOX', (1, -len(clavesRiv)), (-1 + EXTRALEYENDA, -1), 2, colors.black), ] + ESTILOLEYENDA

    listaFilas = [filaCab] + filasTabla

    tStyle = TableStyle(listaEstilos)

    tabla1 = Table(data=listaFilas, style=tStyle, colWidths=LISTAANCHOS, rowHeights=11.2)

    return tabla1

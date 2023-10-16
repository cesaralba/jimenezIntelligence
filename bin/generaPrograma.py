import sys

import numpy as np
from configargparse import ArgumentParser
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Table, SimpleDocTemplate, Paragraph, TableStyle, Spacer, NextPageTemplate, PageTemplate,
                                Frame, PageBreak)
from scipy import stats

import SMACB.Programa
from SMACB.Programa import auxCalculaBalanceStr, estadsEquipoPortada, listaEquipos, paginasJugadores, \
    reportTrayectoriaEquipos, tablaLiga, datosRestoJornada
from SMACB.TemporadaACB import TemporadaACB, precalculaOrdenEstadsLiga, COLSESTADSASCENDING, equipo2clasif
from Utils.FechaHora import Time2Str

estadGlobales = None
estadGlobalesOrden = None
clasifLiga = None

ESTADISTICOEQ = 'mean'
ESTADISTICOJUG = 'mean'
ANCHOTIROS = 16
ANCHOREBOTES = 14

ESTILOS = getSampleStyleSheet()


def cabeceraPortada(partido, tempData):
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = Time2Str(partido['fechaPartido'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - " + f"J: <b>{j}</b><br/>{fh}</para>",
        style)

    cabLocal = datosCabEquipo(datosLocal, tempData, partido['fechaPartido'])
    cabVisit = datosCabEquipo(datosVisit, tempData, partido['fechaPartido'])

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def datosCabEquipo(datosEq, tempData, fecha):
    recuperaClasifLiga(tempData, fecha)

    # TODO: Imagen (descargar imagen de escudo y plantarla)
    nombre = datosEq['nombcorto']

    clasifAux = equipo2clasif(clasifLiga, datosEq['abrev'])
    clasifStr = auxCalculaBalanceStr(clasifAux)

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def recuperaEstadsGlobales(tempData):
    global estadGlobales, estadGlobalesOrden

    if estadGlobales is None:
        estadGlobales = tempData.dfEstadsLiga()
        estadGlobalesOrden = precalculaOrdenEstadsLiga(estadGlobales, COLSESTADSASCENDING)


def recuperaClasifLiga(tempData, fecha=None):
    global clasifLiga

    print(tempData)
    if clasifLiga is None:
        clasifLiga = tempData.clasifLiga(fecha)
        jugados = np.array([eq['Jug'] for eq in clasifLiga])
        modaJug = stats.mode(jugados, keepdims=False).mode

        for eq in clasifLiga:
            if eq['Jug'] != modaJug:
                pendientes = modaJug - eq['Jug']
                aux = "*" if (abs(pendientes) == 1) else pendientes

                eq.update({'pendientes': aux})


def preparaLibro(outfile, tempData, datosSig):
    MARGENFRAME = 2 * mm
    frameNormal = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[0] - 2 * MARGENFRAME, height=A4[1] - 2 * MARGENFRAME,
                        leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                        topPadding=MARGENFRAME)
    frameApaisado = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[1] - 2 * MARGENFRAME, height=A4[0] - 2 * MARGENFRAME,
                          leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                          topPadding=MARGENFRAME)
    pagNormal = PageTemplate('normal', pagesize=A4, frames=[frameNormal], autoNextPageTemplate='normal')
    pagApaisada = PageTemplate('apaisada', pagesize=landscape(A4), frames=[frameApaisado],
                               autoNextPageTemplate='apaisada')

    doc = SimpleDocTemplate(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=5 * mm, leftMargin=5 * mm, rightMargin=5 * mm, topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    story = []

    (sigPartido, abrEqs, juIzda, peIzda, juDcha, peDcha, targLocal) = datosSig
    datosJor = datosRestoJornada(tempData, datosSig)
    exit(1)

    antecedentes = {p.url for p in juIzda}.intersection({p.url for p in juDcha})

    story.append(cabeceraPortada(sigPartido, tempData))

    story.append(Spacer(width=120 * mm, height=2 * mm))
    story.append(estadsEquipoPortada(tempData, abrEqs))

    if antecedentes:
        print("Antecedentes!")

    trayectoria = reportTrayectoriaEquipos(tempData, abrEqs, juIzda, juDcha, peIzda, peDcha)
    if trayectoria:
        story.append(Spacer(width=120 * mm, height=1 * mm))
        story.append(trayectoria)

    story.append(NextPageTemplate('apaisada'))
    story.append(PageBreak())
    story.append(tablaLiga(tempData, equiposAmarcar=abrEqs))

    if (len(juIzda) + len(juDcha)):
        infoJugadores = paginasJugadores(tempData, abrEqs, juIzda, juDcha)
        story.extend(infoJugadores)

    doc.build(story)


def parse_arguments():
    descriptionTXT = "Prepares a booklet for the next game of a team"

    parser = ArgumentParser(description=descriptionTXT)
    parser.add_argument("-t", "--acbfile", dest="acbfile", action="store", required=True, env_var="ACB_FILE",
                        help="Nombre del ficheros de temporada", )
    parser.add_argument("-l", "--listaequipos", dest='listaEquipos', action="store_true", required=False,
                        help="Lista siglas para equipos", )
    parser.add_argument("-q", "--quiet", dest='quiet', action="store_true", required=False,
                        help="En combinación con -l saca lista siglas sin nombres", )

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

    if SMACB.Programa.listaEquipos:
        listaEquipos(tempData, args.quiet)

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

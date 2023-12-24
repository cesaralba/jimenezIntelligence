import sys

from locale import setlocale, LC_ALL

from configargparse import ArgumentParser
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Spacer, NextPageTemplate, PageTemplate, Frame, PageBreak)

from SMACB.Constants import CATESTADSEQASCENDING
from SMACB.Programa import listaEquipos, paginasJugadores, reportTrayectoriaEquipos, tablaLiga, cabeceraPortada, \
    cargaTemporada, tablaAnalisisEstadisticos, tablaClasifLiga, bloqueRestoJYBasics


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
                            initialLeading=2 * mm, leftMargin=3 * mm, rightMargin=3 * mm, topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    story = list()

    sigPartido, abrEqs, juIzda, _, juDcha, _, _ = datosSig
    currJornada = int(sigPartido['jornada'])

    story.append(cabeceraPortada(datosSig, tempData))
    story.append(Spacer(width=120 * mm, height=2 * mm))

    tabEstadsBasicas = bloqueRestoJYBasics(tempData, datosSig)
    story.append(tabEstadsBasicas)
    story.append(Spacer(width=120 * mm, height=2 * mm))

    tabClasif = tablaClasifLiga(tempData, datosSig)
    story.append(tabClasif)
    story.append(Spacer(width=120 * mm, height=2 * mm))

    trayectoria = reportTrayectoriaEquipos(tempData, datosSig)
    if trayectoria:
        story.append(trayectoria)
        story.append(Spacer(width=120 * mm, height=1 * mm))

    story.append(NextPageTemplate('apaisada'))
    story.append(PageBreak())
    story.append(tablaLiga(tempData, equiposAmarcar=abrEqs, currJornada=currJornada))

    if len(juIzda) + len(juDcha):
        infoJugadores = paginasJugadores(tempData, abrEqs, juIzda, juDcha)
        story.extend(infoJugadores)

    story.append(NextPageTemplate('normal'))
    story.append(PageBreak())

    reqData = {
        'Eq': ['P', 'Prec', 'POS', 'OER', 'DER', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-C', 'TC-I', 'TC%',
               'T1-C', 'T1-I', 'T1%', 'eff-t1', 'eff-t2', 'eff-t3', 't3/tc-I', 't3/tc-C', 'ppTC', 'PTC/PTCPot', 'R-D',
               'R-O', 'REB-T', 'EffRebD', 'EffRebO', 'A', 'A/BP', 'A/TC-C', 'BP', 'PNR', 'BR', 'TAP-F', 'TAP-C', 'FP-F',
               'FP-C'],
        'Rival': ['POS', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-C', 'TC-I', 'TC%', 'T1-C', 'T1-I', 'T1%',
                  'eff-t1', 'eff-t2', 'eff-t3', 't3/tc-I', 't3/tc-C', 'ppTC', 'PTC/PTCPot', 'R-D', 'R-O', 'REB-T', 'A',
                  'A/BP', 'A/TC-C', 'BP', 'PNR', 'BR', 'TAP-F', 'TAP-C', 'FP-F', 'FP-C']}
    story.append(
        tablaAnalisisEstadisticos(tempData, datosSig, magns2incl=reqData, magnsCrecientes=CATESTADSEQASCENDING))

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
    parser.add_argument("--locale", dest="locale", action="store", required=False, default='es_ES', help="Locale", )

    result = parser.parse_args()

    return result


def main(args):
    setlocale(LC_ALL, args.locale)
    tempData = cargaTemporada(args.acbfile)

    if args.listaEquipos:
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
    argsCLI = parse_arguments()
    main(argsCLI)

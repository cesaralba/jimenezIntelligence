import sys
from locale import LC_ALL, setlocale

from configargparse import ArgumentParser, Namespace
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (Frame, NextPageTemplate, PageBreak, PageTemplate, SimpleDocTemplate, Spacer)

from SMACB.Constants import CATESTADSEQASCENDING, infoSigPartido
from SMACB.Programa import (auxGeneraLeyendaLiga, bloqueRestoJYBasics, cabeceraPortada, cargaTemporada, listaEquipos,
                            metadataPrograma, paginasJugadores, reportTrayectoriaEquipos, tablaAnalisisEstadisticos,
                            tablaClasifLiga, tablaLiga, preparaListaTablas, )
from SMACB.TemporadaACB import TemporadaACB

MARGENFRAME = 2 * mm
frameNormal = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[0] - 2 * MARGENFRAME, height=A4[1] - 2 * MARGENFRAME,
                    leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                    topPadding=MARGENFRAME)
frameApaisado = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[1] - 2 * MARGENFRAME, height=A4[0] - 2 * MARGENFRAME,
                      leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                      topPadding=MARGENFRAME)
pagNormal = PageTemplate('normal', pagesize=A4, frames=[frameNormal], autoNextPageTemplate='normal')
pagApaisada = PageTemplate('apaisada', pagesize=landscape(A4), frames=[frameApaisado], autoNextPageTemplate='apaisada')


def preparaLibro(args: Namespace, tempData: TemporadaACB, datosSig: infoSigPartido):
    doc = SimpleDocTemplate(filename=args.outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=2 * mm, leftMargin=3 * mm, rightMargin=3 * mm, topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    story = []

    # Pagina 1
    story.append(cabeceraPortada(tempData, datosSig))
    story.append(Spacer(width=120 * mm, height=1 * mm))
    story.append(metadataPrograma(tempData))
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

    # Pagina 2
    story.append(NextPageTemplate('apaisada'))
    story.append(PageBreak())

    story.append(tablaLiga(tempData, equiposAmarcar=datosSig.abrevLV, currJornada=int(datosSig.sigPartido['jornada'])))
    story.append(auxGeneraLeyendaLiga())

    # Paginas 3 y 4
    tablasAmostrar = preparaListaTablas(args.tablasJugs)
    if tablasAmostrar:
        if len(datosSig.jugLocal) + len(datosSig.jugVis):
            infoJugadores = paginasJugadores(tempData, datosSig.abrevLV, datosSig.jugLocal, datosSig.jugVis,
                                             tablasAmostrar)
            story.extend(infoJugadores)

    story.append(NextPageTemplate('normal'))
    story.append(PageBreak())

    # Pagina 5
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
    # Fin del doc

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

    parser.add_argument("-f", "--tablajugs", dest='tablasJugs', action="store", required=False, env_var="PROG_TABLA",
                        default='TOT,PROM', help="Lista de tablas a incluir en información de jugadores", )
    parser.add_argument("-o", "--outfile", dest="outfile", action="store", help="Fichero PDF generado",
                        required=False, )

    parser.add_argument("-c", "--cachedir", dest="cachedir", action="store", required=False, env_var="ACB_CACHEDIR",
                        help="Ubicación de caché de ficheros", )
    parser.add_argument("--locale", dest="locale", action="store", required=False, default='es_ES', help="Locale", )

    result = parser.parse_args()

    if preparaListaTablas(result.tablasJugs) is None:
        parser.exit("Parametro incorrecto en lista de tablas.")

    return result


def main(args):
    setlocale(LC_ALL, args.locale)
    tempData = cargaTemporada(args.acbfile)

    if args.listaEquipos:
        listaEquipos(tempData, args.quiet)

    REQARGS = ['equipo', 'outfile']
    missingReqs = {k for k in REQARGS if (k not in args) or (getattr(args, k) is None)}
    if missingReqs:
        missingReqsStr = ",".join(sorted(missingReqs))
        print(f"Faltan argumentos (ver -h): {missingReqsStr}")
        sys.exit(1)
    try:
        datosSig: infoSigPartido = tempData.sigPartido(args.equipo)
    except KeyError as exc:
        print(f"Equipo desconocido '{args.equipo}': {exc}")
        sys.exit(1)

    preparaLibro(args, tempData, datosSig)


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

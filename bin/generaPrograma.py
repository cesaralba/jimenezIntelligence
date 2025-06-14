import sys
from locale import LC_ALL, setlocale

from configargparse import ArgumentParser, Namespace
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate)

from SMACB.Constants import infoSigPartido
from SMACB.Programa.Constantes import pagNormal, pagApaisada
from SMACB.Programa.Funciones import listaEquipos, preparaListaTablas
from SMACB.Programa.Paginas import paginaPortada, paginaCruces, paginaPartidosLiga, paginaJugadores, paginaEstadsEquipos
from SMACB.TemporadaACB import TemporadaACB, cargaTemporada


def preparaLibro(args: Namespace, tempData: TemporadaACB, datosSig: infoSigPartido):
    doc = SimpleDocTemplate(filename=args.outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=2 * mm, leftMargin=3 * mm, rightMargin=3 * mm, topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    story = []

    # # Pagina 1
    story.extend(paginaPortada(tempData, datosSig))
    #
    # # # Pagina 2
    # story.extend(paginaPartidosLiga(tempData, datosSig))

    # Paginas 3 y 4
    # story.extend(paginaJugadores(tempData, datosSig, args.tablasJugs))

    # Pagina 5
    # story.extend(paginaEstadsEquipos(tempData, datosSig))
    #
    # story.extend(paginaCruces(tempData))
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
    except IndexError:
        print(f"Equipo '{args.equipo}': no tiene más partidos conocidos")
        sys.exit(1)

    preparaLibro(args, tempData, datosSig)


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

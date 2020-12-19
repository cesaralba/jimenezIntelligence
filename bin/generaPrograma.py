from copy import copy

import reportlab.lib.colors as colors
import sys
from configargparse import ArgumentParser
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Table, SimpleDocTemplate, Paragraph, TableStyle
from time import strftime

from SMACB.PartidoACB import LocalVisitante, OtherTeam
from SMACB.TemporadaACB import TemporadaACB
from Utils.FechaHora import Time2Str


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
    strResultado = "-".join(resAux)

    return strRival, strResultado


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


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def listaEquipos(tempData):
    print("Abreviatura -> nombre(s) equipo")
    for abr in sorted(tempData.Calendario.tradEquipos['c2n']):
        listaEquiposAux = sorted(tempData.Calendario.tradEquipos['c2n'][abr], key=lambda x: (len(x), x), reverse=True)
        listaEquiposStr = ",".join(listaEquiposAux)
        print(f'{abr}: {listaEquiposStr}')
    sys.exit(0)


def cabEquipo(datosEq, tempData, fecha):
    # TODO: Imagen
    nombre = datosEq['nombcorto']

    if tempData:
        clasifAux = tempData.clasifEquipo(datosEq['abrev'], fecha)
        clasifStr = "(%i-%i)" % (clasifAux.get('V', 0), clasifAux.get('D', 0))

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'>{nombre}</para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


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

    cabLocal = cabEquipo(datosLocal, tempData, partido['fecha'])
    cabVisit = cabEquipo(datosVisit, tempData, partido['fecha'])

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


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

    t = Table(data=filas, style=tStyle,colWidths=[20 * mm, 75 * mm, 10 * mm, 75 * mm, 20 * mm])

    return t


def preparaLibro(outfile, tempData, datosSig):
    doc = SimpleDocTemplate(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=5 * mm,
                            leftMargin=5 * mm,
                            rightMargin=5 * mm,
                            topMargin=5 * mm,
                            bottomMargin=5 * mm)
    # pdfFile = canvas.Canvas(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',                            initialLeading=0.5 * mm)
    story = []

    (sigPartido, abrEqs, juEq, peEq, juRiv, peRiv) = datosSig

    antecedentes = {p.url for p in juEq}.intersection({p.url for p in juRiv})

    iSigLocal = list(tempData.Calendario.tradEquipos['c2i'][sigPartido['loc2abrev']['Local']])[0]
    targLocal = args.equipo in tempData.Calendario.tradEquipos['i2c'][iSigLocal]
    juIzda, juDcha = (juEq, juRiv) if targLocal else (juRiv, juEq)

    mezParts = mezclaPartJugados(tempData, abrEqs, juIzda, juDcha)

    story.append(cabeceraPortada(sigPartido, tempData))

    if antecedentes:
        print("Antecedentes!")
    else:
        aux = Paragraph("Sin antecedentes esta temporada")
        story.append(aux)

    if mezParts:
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

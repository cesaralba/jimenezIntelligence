import argparse
import sys
from copy import copy
from time import strftime

from SMACB.PartidoACB import LocalVisitante, OtherTeam
from SMACB.TemporadaACB import TemporadaACB


def partidoTrayectoria(partido, abrevs, datosTemp):
    #Cadena de información del partido
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
    prefV = {loc: '*' if partido.DatosSuministrados['equipos'][loc]['haGanado'] else '' for loc in LocalVisitante}
    prefMe = {loc: '_' if (loc == locEq) else '' for loc in LocalVisitante}
    resAux = [f"{prefV[loc]}{prefMe[loc]}{partido.DatosSuministrados['resultado'][loc]}{prefMe[loc]}{prefV[loc]}" for loc in LocalVisitante]
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
        listaEquipos = sorted(tempData.Calendario.tradEquipos['c2n'][abr], key=lambda x: (len(x), x), reverse=True)
        listaEquiposStr = ",".join(listaEquipos)
        print(f'{abr}: {listaEquiposStr}')
    sys.exit(0)


def parse_arguments():
    descriptionTXT = "Merges POIs with the geographical entities used by Smart Steps"

    parser = argparse.ArgumentParser(description=descriptionTXT, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-t", "--acbfile", dest="acbfile", action="store", required=True, help="Nombre del ficheros de temporada", )
    parser.add_argument("-l", "--listaequipos", dest='listaEquipos', action="store_true", required=False, help="Lista siglas para equipos", )

    parser.add_argument("-e", "--equipo", dest="equipo", action="store", required=False, help="Abreviatura del equipo deseado (usar -l para obtener lista)", )
    parser.add_argument("-o", "--outfile", dest="outfile", action="store", help="Fichero PDF generado", required=False, )

    args = parser.parse_args()

    return args


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
        (sigPartido, abrEqs, juEq, peEq, juRiv, peRiv) = tempData.sigPartido(args.equipo)
    except KeyError as exc:
        print(f"Equipo desconocido '{args.equipo}': {exc}")
        sys.exit(1)

    print(sigPartido)

    raise Exception("Bye")


if __name__ == '__main__':
    args = parse_arguments()
    main(args)

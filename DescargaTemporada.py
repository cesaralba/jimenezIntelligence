#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from typing import Dict

from CAPcore.Logging import prepareLogger
from CAPcore.Web import createBrowser, extractGetParams
from configargparse import ArgumentParser, Namespace

from SMACB.CalendarioACB import calendario_URLBASE
from SMACB.PlantillaACB import CambiosPlantillaTipo
from SMACB.TemporadaACB import TemporadaACB, CAMBIOSJUGADORES, CAMBIOSCLUB


def parse_arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, help='Salida más detallada',
               default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, help='Salida más detallada',
               default=False)
    parser.add('-j', dest='justone', action="store_true", env_var='SM_JUSTONE', required=False,
               help='Solo descarga un partido', default=False)
    parser.add('-f', dest='saveanyway', action="store_true", env_var='SM_SAVEANYWAY', required=False,
               help='Graba el fichero aunque no haya habido cambios', default=False)
    parser.add('-r', dest='refresh', action="store_true", env_var='SM_REFRESH', required=False,
               help='Recarga las fichas de jugadores', default=False)
    parser.add('-e', dest='edicion', action="store", env_var='SM_EDICION', required=False,
               help=('Año de la temporada (para 2015-2016 sería 2016). La ACB empieza en 1983. '
                     'La copa se referencia por el año menor '), default=None)
    parser.add('-c', dest='competicion', action="store", env_var='SM_COMPETICION', required=False,
               choices=['LACB', 'COPA', 'SCOPA'], help='Clave de la competición: Liga=LACB, Copa=COPA, Supercopa=SCOPA',
               default="LACB")
    parser.add('-u', dest='url', action="store", env_var='SM_URLCAL', help='', required=False)
    parser.add('-b', dest='procesaBio', action="store_true", env_var='SM_STOREBIO',
               help='Descarga los datos biográficos de los jugadores', required=False, default=False)
    parser.add('-p', dest='procesaPlantilla', action="store_true", env_var='SM_STOREPLANT',
               help='Descarga las plantillas de los equipos', required=False, default=False)
    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', help='Fichero de entrada', required=False)
    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', help='Fichero de salida', required=False)
    args = parser.parse_args()

    return args


def resumenCambioJugadores(cambiosJugadores: dict, temporada: TemporadaACB):
    jugList = []
    for jugCod, jugData in cambiosJugadores.items():
        if not jugData:
            continue
        ultClub = temporada.fichaJugadores[jugCod].ultClub
        clubStr = "" if ultClub is None else f"{temporada.plantillas[ultClub].nombreClub()} "

        jugadorStr = f"{temporada.fichaJugadores[jugCod].nombreFicha()}"
        if 'NuevoJugador' in jugData:
            jugList.append(f"* {jugadorStr} Nuevo fichaje de {clubStr}")
        else:
            claves2skip = {'urlFoto'}
            tradClaves = {'licencia': 'Cupo', 'nacionalidad': 'Pais', 'lugarNac': 'Origen', 'nombre': 'Nombre'}
            cambiosJug = []
            for k, v in jugData.items():
                if (k in claves2skip) or (v[0] is None):
                    continue
                if k == 'ultClub':
                    if v[1] is None:
                        cambioStr = f"Club: baja en {temporada.plantillas[v[0]].nombreClub()}"
                    else:
                        club1 = temporada.plantillas[v[1]].nombreClub()
                        cambioStr = f"Club: {temporada.plantillas[v[0]].nombreClub()} -> {club1}"
                else:
                    cambioStr = f"{tradClaves.get(k, k)}: '{v[0]}'->'{v[1]}'"

                cambiosJug.append(cambioStr)
            if 'urlFoto' in jugData:
                cambiosJug.append("Nueva foto")
            if len(cambiosJug) == 0:
                continue
            jugList.append(f"* {jugadorStr} {clubStr}Cambios: {','.join(sorted(cambiosJug))}")

    print(f"Cambios en jugadores:\n{'\n'.join(sorted(jugList))}")


def muestraResumenPartidos(nuevosPartidos, temporada):
    resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos), key=lambda p: (
        temporada.Partidos[p].fechaPartido, temporada.Partidos[p].jornada))]
    print("Nuevos partidos incorporados:\n%s" % ("\n".join(resumenPartidos)))


def textoJugador(temporada: TemporadaACB, idJug: str):
    return f"{temporada.fichaJugadores[idJug].nombreFicha()}"


def dataPlantJug(temporada: TemporadaACB, idJug: str, idClub: str):
    return temporada.plantillas[idClub].jugadores._asdict()[idJug]


def dataPlantTec(temporada: TemporadaACB, idTec: str, idClub: str):
    return temporada.plantillas[idClub].tecnicos._asdict()[idTec]


def textoTecnico(temporada: TemporadaACB, idTec: str, idClub: str):
    auxInfo = dataPlantTec(temporada, idTec, idClub)
    return f"ENT[{auxInfo['dorsal']}] {auxInfo.get('alias', auxInfo.get('nombre', 'NONAME'))}"


def resumenCambioClubes(cambiosClubes: Dict[str, CambiosPlantillaTipo], temporada: TemporadaACB):
    listaCambios = []

    for cl, cambios in cambiosClubes.items():
        if not (cambios.jugadores or cambios.tecnicos or cambios.club):
            continue
        nombreClub = temporada.plantillas[cl].nombreClub()

        cambiosClubList = []

        if cambios.club:
            cambiosClubList.append(f"Cambio en datos del club: {cambios.club.show(compact=True)}")

        if cambios.jugadores:
            cambioJugsList = preparaResumenPlantillasJugadores(cambios, cl, temporada)

            if cambioJugsList:
                lineaJugadores = "Cambio en jugadores:\n" + "\n".join(sorted(cambioJugsList))
                cambiosClubList.append(lineaJugadores)

        if cambios.tecnicos:
            cambioTecList = preparaResumenPlantillasTecnicos(cambios, cl, temporada)

            if cambioTecList:
                lineaTecnicos = "Cambio en técnicos:\n" + "\n".join(sorted(cambioTecList))
                cambiosClubList.append(lineaTecnicos)

        if cambiosClubList:
            lineaClub = f"CLUB '{nombreClub}' [{cl}]:\n" + "\n".join(cambiosClubList)
            listaCambios.append(lineaClub)

    if listaCambios:
        print("CAMBIOS EN PLANTILLAS:\n" + "\n".join(sorted(listaCambios)))


def preparaResumenPlantillasTecnicos(cambios, cl, temporada):
    cambioTecList = []

    for idJug in cambios.tecnicos.added:
        cambioTecList.append(f"  * Alta: {textoTecnico(temporada, idJug, cl)}")

    for idJug, dataJug in cambios.tecnicos.changed.items():
        auxDiffchanged = dataJug.changed
        if not auxDiffchanged:
            continue
        if ('activo' in auxDiffchanged) and (not auxDiffchanged['activo'][1]):
            cambioTecList.append(f"  * Baja: {textoTecnico(temporada, idJug, cl)}")
        else:
            changeStr = ",".join(
                [f"{k}: '{auxDiffchanged[k][0]}'->'{auxDiffchanged[k][1]}'" for k in sorted(auxDiffchanged.keys())])
            cambioTecList.append(f"  * Cambios: {textoTecnico(temporada, idJug, cl)}: {changeStr}")

    for idJug, dataJug in cambios.tecnicos.removed.items():
        cambioTecList.append(f"  * BORRADO:{textoTecnico(temporada, idJug, cl)}")
    return cambioTecList


def preparaResumenPlantillasJugadores(cambios, cl, temporada):
    cambioJugsList = []
    for idJug in cambios.jugadores.added:
        dorsal = dataPlantJug(temporada, idJug, cl)['dorsal']
        cambioJugsList.append(f"  * Alta: {textoJugador(temporada, idJug)} dorsal:[{dorsal}]")
    for idJug, dataJug in cambios.jugadores.changed.items():
        auxJug = dataPlantJug(temporada, idJug, cl)
        dorsal = auxJug['dorsal']
        auxDiffchanged = dataJug.changed
        if not auxDiffchanged:
            continue
        if ('activo' in auxDiffchanged) and (not auxDiffchanged['activo'][1]):
            cambioJugsList.append(f"  * Baja: {textoJugador(temporada, idJug)} Dorsal: {dorsal}")
        else:
            changeStr = ",".join(
                [f"{k}: '{auxDiffchanged[k][0]}'->'{auxDiffchanged[k][1]}'" for k in sorted(auxDiffchanged.keys())])
            cambioJugsList.append(f"  * Cambios: {textoJugador(temporada, idJug)} Dorsal: {dorsal}: {changeStr}")

    for idJug, dataJug in cambios.jugadores.removed.items():
        auxJug = dataPlantJug(temporada, idJug, cl)
        dorsal = auxJug['dorsal']
        cambioJugsList.append(f"  * BORRADO: {textoJugador(temporada, idJug)} Dorsal: {dorsal}")

    return cambioJugsList


def main(args: Namespace):
    browser = createBrowser(config=args)
    preparaLogs(args)

    sourceURL = args.url or calendario_URLBASE

    if args.edicion is not None:
        parEdicion = args.edicion
        parCompeticion = args.competicion
    else:
        paramsURL = extractGetParams(sourceURL)
        parCompeticion = paramsURL['cod_competicion']
        parEdicion = paramsURL['cod_edicion']

    temporada = TemporadaACB(competicion=parCompeticion, edicion=parEdicion, urlbase=sourceURL)
    ajustaInternalsTemporada(args, temporada)

    nuevosPartidos = temporada.actualizaTemporada(browser=browser, config=args)
    resultOS = 1  # No hubo cambios
    if nuevosPartidos or temporada.changed or args.saveanyway:
        sys.setrecursionlimit(50000)
        if 'outfile' in args and args.outfile:
            resultOS = 0
            temporada.grabaTemporada(args.outfile)

    if nuevosPartidos:
        muestraResumenPartidos(nuevosPartidos, temporada)

    if CAMBIOSJUGADORES:
        resumenCambioJugadores(CAMBIOSJUGADORES, temporada=temporada)

    if CAMBIOSCLUB:
        resumenCambioClubes(CAMBIOSCLUB, temporada=temporada)

    sys.exit(resultOS)


def ajustaInternalsTemporada(args, temporada):
    if 'infile' in args and args.infile:
        temporada.cargaTemporada(args.infile)
    if 'procesaBio' in args and args.procesaBio and not temporada.descargaFichas:
        temporada.descargaFichas = True
        temporada.changed = True
    if 'procesaPlantilla' in args and args.procesaPlantilla and not temporada.descargaPlantillas:
        temporada.descargaPlantillas = True
        temporada.changed = True


def preparaLogs(args: Namespace):
    logger = logging.getLogger()
    if args.debug:
        prepareLogger(logger=logger, level=logging.DEBUG)
    elif args.verbose:
        prepareLogger(logger=logger, level=logging.INFO)
    else:
        prepareLogger(logger=logger)


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

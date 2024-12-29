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
    global args
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


def resumenCambioJugadores(cambiosJugadores:dict,temporada:TemporadaACB):
    global jugList
    jugList = []
    for jugCod, jugData in cambiosJugadores.items():
        if not jugData:
            continue
        if 'NuevoJugador' in jugData:
            jugList.append(f"{jugCod} Nuevo : {temporada.fichaJugadores[jugCod]}")
        else:
            claves2skip = {'urlFoto'}
            cambiosJusg = [f"{k}: '{v[0]}'->'{v[1]}'" for k, v in jugData.items() if k not in claves2skip]
            if 'urlFoto' in jugData:
                cambiosJusg.append("Nueva foto")
            jugList.append(f"{jugCod} Cambios: {temporada.fichaJugadores[jugCod]}: {','.join(sorted(cambiosJusg))}")

    print(f"Cambios en jugadores:\n{'\n'.join(sorted(jugList))}")


def muestraResumenPartidos(nuevosPartidos, temporada):
    resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos), key=lambda p: (
        temporada.Partidos[p].fechaPartido, temporada.Partidos[p].jornada))]
    print("Nuevos partidos incorporados:\n%s" % ("\n".join(resumenPartidos)))


def resumenCambioClubes(cambiosClubes:Dict[str,CambiosPlantillaTipo],temporada:TemporadaACB):
    listaCambios= []
    for cl,cambios in cambiosClubes.items():
        nombreClub = temporada.plantillas[cl].nombreClub()
        cambiosStr = f"Club '{nombreClub}':"
        print(cambiosStr)
        if cambios.club:
            cambiosStr += "  Datos club:\n" + cambios.club.show(compact=False,indent=4)
        if cambios.jugadores:
            cambiosStr += "  Jugadores:\n" #+ cambios.jugadores.show(compact=False,indent=4)
            #print([k for k in dir(cambios.jugadores) if not k.startswith('__')])
            if cambios.jugadores.added:
                print("Added", type(cambios.jugadores.added))
                for idJug,dataJug in cambios.jugadores.added.items():
                    print(temporada.fichaJugadores[idJug],dataJug)
            if cambios.jugadores.changed:
                print("changed", type(cambios.jugadores.changed))
                for idJug,dataJug in cambios.jugadores.changed.items():
                    print(temporada.fichaJugadores[idJug],type(dataJug))
            if cambios.jugadores.removed:
                print("removed", type(cambios.jugadores.removed))
                for idJug,dataJug in cambios.jugadores.removed.items():
                    print(temporada.fichaJugadores[idJug],type(dataJug))

        if cambios.tecnicos:
            cambiosStr += "  Técnicos:\n" #+ cambios.tecnicos.show(compact=False,indent=4)
            print([k for k in dir(cambios.tecnicos) if not k.startswith('__')])

        print(cambiosStr)
        #listaCambios.append((nombreClub,"\n".join(cambiosStr)))

    #print(f"Cambios en clubes:\n"+"\n".join([s for k,s in sorted(listaCambios)]))


def main(args: Namespace):
    global temporada
    browser = createBrowser(config=args)
    preparaLogs(args)

    if args.url is not None:
        sourceURL = args.url
    else:
        sourceURL = calendario_URLBASE
    if args.edicion is not None:
        parEdicion = args.edicion
        parCompeticion = args.competicion
    else:
        paramsURL = extractGetParams(sourceURL)
        parCompeticion = paramsURL['cod_competicion']
        parEdicion = paramsURL['cod_edicion']
    temporada = TemporadaACB(competicion=parCompeticion, edicion=parEdicion, urlbase=sourceURL)
    if 'infile' in args and args.infile:
        temporada.cargaTemporada(args.infile)
    if 'procesaBio' in args and args.procesaBio and not temporada.descargaFichas:
        temporada.descargaFichas = True
        temporada.changed = True
    if 'procesaPlantilla' in args and args.procesaPlantilla and not temporada.descargaPlantillas:
        temporada.descargaPlantillas = True
        temporada.changed = True
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
        resumenCambioJugadores(CAMBIOSJUGADORES,temporada=temporada)

    if CAMBIOSCLUB:
        resumenCambioClubes(CAMBIOSCLUB,temporada=temporada)

    sys.exit(resultOS)


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

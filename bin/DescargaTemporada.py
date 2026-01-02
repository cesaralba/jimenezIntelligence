#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from pprint import pp

from CAPcore.Logging import prepareLogger
from CAPcore.Web import createBrowser, extractGetParams
from configargparse import ArgumentParser, Namespace

from SMACB.CalendarioACB import calendario_URLBASE
from SMACB.DiferenciasTrasDescargaTemp import resumenCambioJugadores, resumenNuevosPartidos, resumenCambioClubes, \
    resumenCambiosCalendario
from SMACB.TemporadaACB import TemporadaACB, CAMBIOSCLUB, CAMBIOSCALENDARIO, CAMBIOSENTRENADORES, CAMBIOSJUGADORES
from Utils.ManageArgs import createArgs


def parse_arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, help='Salida más detallada',
               default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, help='Salida más detallada',
               default=False)
    parser.add('-j', dest='justone', action="store_true", env_var='SM_JUSTONE', required=False,
               help='Solo descarga un partido', default=False)
    parser.add('-l', '--limit', dest='limit', action="store", env_var='SM_LIMIT', required=False, type=int,
               help='Número máximo de partidos a descargar', default=0)
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
    finalArgs = procesaParamsTemporada(temporada, args)

    nuevosPartidos = temporada.actualizaTemporada(browser=browser, config=finalArgs)
    if nuevosPartidos or temporada.changed or getattr(finalArgs, 'saveanyway'):
        sys.setrecursionlimit(50000)
        if getattr(finalArgs, 'outfile'):
            temporada.grabaTemporada(getattr(finalArgs, 'outfile'))

    if nuevosPartidos:
        maxPartidosABajar = 1 if (args.justone and not args.limit) else args.limit
        limitStr=f" (limite: {maxPartidosABajar} partidos)" if maxPartidosABajar else ""
        print(f"Partidos descargados{limitStr}\n{resumenNuevosPartidos(nuevosPartidos, temporada)}", "\n" * 2)

    if CAMBIOSJUGADORES:
        pp(CAMBIOSJUGADORES)
        print(f"Cambios en jugadores\n{resumenCambioJugadores(CAMBIOSJUGADORES, temporada=temporada)}", "\n" * 2)

    if CAMBIOSENTRENADORES:
        print("Aqui!")
        pp(CAMBIOSENTRENADORES)
    else:
        print("No")

    if CAMBIOSCLUB:
        print(f"Cambios en plantillas\n{resumenCambioClubes(CAMBIOSCLUB, temporada=temporada)}", "\n" * 2)

    if CAMBIOSCALENDARIO:
        print(f"Cambios en calendario\n{resumenCambiosCalendario(CAMBIOSCALENDARIO, temporada=temporada)}", "\n" * 2)


def procesaParamsTemporada(temporada, args) -> Namespace:
    if args.infile:
        temporada.cargaTemporada(args.infile)
    if args.procesaBio and not temporada.descargaFichas:
        temporada.descargaFichas = True
        temporada.changed = True
    if args.procesaPlantilla and not temporada.descargaPlantillas:
        temporada.descargaPlantillas = True
        temporada.changed = True

    result = createArgs(args, temporada.getConfig())

    return result


def preparaLogs(args: Namespace):
    logger = logging.getLogger()
    if getattr(args, 'debug'):
        prepareLogger(logger=logger, level=logging.DEBUG)
    elif getattr(args, 'verbose'):
        prepareLogger(logger=logger, level=logging.INFO)
    else:
        prepareLogger(logger=logger)


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

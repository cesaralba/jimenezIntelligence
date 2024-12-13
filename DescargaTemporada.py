#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys

from CAPcore.Logging import prepareLogger
from CAPcore.Web import createBrowser, extractGetParams
from configargparse import ArgumentParser

from SMACB.CalendarioACB import calendario_URLBASE
from SMACB.TemporadaACB import TemporadaACB, CAMBIOSJUGADORES

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

browser = createBrowser(config=args)

logger = logging.getLogger()
if args.debug:
    prepareLogger(logger=logger, level=logging.DEBUG)
elif args.verbose:
    prepareLogger(logger=logger, level=logging.INFO)
else:
    prepareLogger(logger=logger)

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
        resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos), key=lambda p: (
            temporada.Partidos[p].fechaPartido, temporada.Partidos[p].jornada))]
        print("Nuevos partidos incorporados:\n%s" % ("\n".join(resumenPartidos)))

    if CAMBIOSJUGADORES:
        jugList = []
        for jugCod, jugData in CAMBIOSJUGADORES.items():
            if not jugData:
                continue
            if 'NuevoJugador' in jugData:
                jugList.append(f"{jugCod} Nuevo : {temporada.fichaJugadores[jugCod]}")
            else:
                claves2skip = set()
                cambiosJusg = [f"{k}: '{v[0]}'->'{v[1]}'" for k, v in jugData.items() if k not in claves2skip]
                jugList.append(f"{jugCod} Cambios: {temporada.fichaJugadores[jugCod]}: {','.join(sorted(cambiosJusg))}")

        print(f"Cambios en jugadores:\n{'\n'.join(sorted(jugList))}")

sys.exit(resultOS)

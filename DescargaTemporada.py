#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from configargparse import ArgumentParser
from mechanicalsoup import StatefulBrowser

from SMACB.CalendarioACB import calendario_URLBASE
from SMACB.TemporadaACB import TemporadaACB
from Utils.Web import ExtraeGetParams

parser = ArgumentParser()
parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, help='', default=0)
parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, help='', default=False)
parser.add('-j', dest='justone', action="store_true", env_var='SM_JUSTONE', required=False,
           help='Solo descarga un partido', default=False)
parser.add('-f', dest='saveanyway', action="store_true", env_var='SM_SAVEANYWAY', required=False,
           help='Graba el fichero aunque no haya habido cambios', default=False)

parser.add('-e', dest='edicion', action="store", env_var='SM_EDICION', required=False,
           help='Año de la temporada (para 2015-2016 sería 2016). La ACB empieza en 1983. La copa se referencia por el año menor ',
           default=None)
parser.add('-c', dest='competicion', action="store", env_var='SM_COMPETICION', required=False,
           choices=['LACB', 'COPA', 'SCOPA'], help='Clave de la competición: Liga=LACB, Copa=COPA, Supercopa=SCOPA',
           default="LACB")
parser.add('-u', dest='url', action="store", env_var='SM_URLCAL', help='', required=False)
parser.add('-b', dest='procesaBio', action="store_true", env_var='SM_STOREBIO',
           help='Descarga los datos biográficos de los jugadores', required=False, default=False)

parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', help='Fichero de entrada', required=False)
parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', help='Fichero de salida', required=False)

args = parser.parse_args()

browser = StatefulBrowser(soup_config={'features': "html.parser"}, raise_on_404=True, user_agent="SMparser", )

if args.url is not None:
    sourceURL = args.url
else:
    sourceURL = calendario_URLBASE

if args.edicion is not None:
    parEdicion = args.edicion
    parCompeticion = args.competicion
else:
    paramsURL = ExtraeGetParams(sourceURL)
    parCompeticion = paramsURL['cod_competicion']
    parEdicion = paramsURL['cod_edicion']

temporada = TemporadaACB(competicion=parCompeticion, edicion=parEdicion, urlbase=sourceURL)

if 'infile' in args and args.infile:
    temporada.cargaTemporada(args.infile)

if 'procesaBio' in args and args.procesaBio:
    if not temporada.descargaFichas:
        temporada.descargaFichas = True
        temporada.changed = True

# sm = SuperManagerACB(config=args)
nuevosPartidos = temporada.actualizaTemporada(browser=browser, config=args)

if nuevosPartidos or args.saveanyway:
    if nuevosPartidos:
        resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos))]
        print("Nuevos partidos incorporados:\n%s" % ("\n".join(resumenPartidos)))

    sys.setrecursionlimit(50000)
    if 'outfile' in args and args.outfile:
        temporada.grabaTemporada(args.outfile)

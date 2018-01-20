#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from configargparse import ArgumentParser
from mechanicalsoup import StatefulBrowser

from SMACB.CalendarioACB import BuscaCalendario
from SMACB.TemporadaACB import TemporadaACB
from Utils.Web import ExtraeGetParams

parser = ArgumentParser()
parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)
parser.add('-j', dest='justone', action="store_true", env_var='SM_JUSTONE', required=False, default=False)

parser.add('-e', dest='edicion', action="store", env_var='SM_EDICION', required=False, default=None)
# parser.add('-c', dest='competicion', action="store", env_var='SM_COMPETICION', required=False, default=None)

parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

args = parser.parse_args()

browser = StatefulBrowser(soup_config={'features': "html.parser"}, raise_on_404=True, user_agent="SMparser",)

sourceURL = BuscaCalendario(browser=browser, config=args)

if args.edicion is not None:
    parEdicion = args.edicion
else:
    paramsURL = ExtraeGetParams(sourceURL)
    parEdicion = paramsURL['cod_edicion']

temporada = TemporadaACB(competition="LACB", edition=parEdicion, urlbase=sourceURL)

if 'infile' in args and args.infile:
    temporada.cargaTemporada(args.infile)

# sm = SuperManagerACB(config=args)
nuevosPartidos = temporada.actualizaTemporada(browser=browser, config=args)

if nuevosPartidos:
    resumenPartidos = [temporada.Partidos[x].resumenPartido() for x in sorted(list(nuevosPartidos))]

    print("Nuevos partidos incorporados:\n%s" % ("\n".join(resumenPartidos)))
    sys.setrecursionlimit(50000)
    if 'outfile' in args and args.outfile:
        temporada.grabaTemporada(args.outfile)

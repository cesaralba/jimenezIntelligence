#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser
from mechanicalsoup import StatefulBrowser

from SMACB.CalendarioACB import BuscaCalendario, CalendarioACB
from SMACB.PartidoACB import PartidoACB
from Utils.Web import ExtraeGetParams

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)
    parser.add('-j', dest='justone', action="store_true", env_var='SM_JUSTONE', required=False, default=False)

    parser.add('-e', dest='edicion', action="store", env_var='SM_EDICION', required=False, default=None)
    # parser.add('-c', dest='competicion', action="store", env_var='SM_COMPETICION', required=False, default=None)

    # parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
    # parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

    args = parser.parse_args()

    browser = StatefulBrowser(soup_config={'features': "html.parser"}, raise_on_404=True, user_agent="SMparser",)

    sourceURL = BuscaCalendario(browser=browser, config=args)

    if args.edicion is not None:
        calendario = CalendarioACB(edition=args.edicion, urlbase=sourceURL)
    else:
        paramsURL = ExtraeGetParams(sourceURL)
        calendario = CalendarioACB(edition=paramsURL['cod_edicion'], urlbase=sourceURL)

    # calendario = CalendarioACB(edition=56, urlbase=sourceURL)
    calendario.BajaCalendario(browser=browser, config=args)

    if 0:
        print(calendario.codigo2equipo)
        print(calendario.equipo2codigo)
        print(calendario.__dict__)
        exit(1)

    Partidos = {'descargados': set(), 'informacion': {}}
    partidosBajados = set()

    for partido in calendario.Partidos:
        if partido in Partidos['descargados']:
            continue

        nuevoPartido = PartidoACB(**(calendario.Partidos[partido]))
        nuevoPartido.DescargaPartido(home=None, browser=browser, config=args)

        Partidos['descargados'].add(partido)
        Partidos['informacion'][partido] = nuevoPartido
        partidosBajados.add(partido)
        print("PARTIDO:  ", nuevoPartido.__dict__)
        if args.justone:
            exit(1)

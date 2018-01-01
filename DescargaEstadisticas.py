#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser
from mechanicalsoup import StatefulBrowser

from SMACB.CalendarioACB import BuscaCalendario, CalendarioACB
from Utils.Web import ExtraeGetParams

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)
    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

    # parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()

    browser = StatefulBrowser(soup_config={'features': "html.parser"}, raise_on_404=True, user_agent="SMparser",)

    sourceURL = BuscaCalendario(browser=browser, config=args)
    paramsURL = ExtraeGetParams(sourceURL)

    calendario = CalendarioACB(edition=paramsURL['cod_edicion'], urlbase=sourceURL)
#    calendario = CalendarioACB(edition=30, urlbase=sourceURL)
    calendario.BajaCalendario(browser=browser, config=args)

    # print(calendario.__dict__)
    exit(1)

    cal = CalendarioACB(config=args)
    cal.BajaCalendario()

#     if 'infile' in args and args.infile:
#         sm.loadData(args.infile)
#
#     #sm = SuperManagerACB(config=args)
#     sm.Connect()
#
#     sm.getSMstatus()
#
#     if sm.changed and ('outfile' in args and args.outfile):
#         print("There were changes!")
#         sm.saveData(args.outfile)

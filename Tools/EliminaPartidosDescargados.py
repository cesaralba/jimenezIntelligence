#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from operator import attrgetter

from CAPcore.Logging import prepareLogger
from configargparse import ArgumentParser, Namespace

from SMACB.TemporadaACB import TemporadaACB


def parse_arguments() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False,
                        help='Salida más detallada',
                        default=0)
    parser.add_argument('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False,
                        help='Salida más detallada',
                        default=False)

    parser.add_argument('-i', dest='infile', type=str, env_var='SM_INFILE', help='Fichero de entrada', required=True)
    parser.add_argument('-o', dest='outfile', type=str, env_var='SM_OUTFILE', help='Fichero de salida', required=True)

    parser.add_argument(nargs='*', dest='partidos')
    args = parser.parse_args()

    return args


def main(args: Namespace):
    preparaLogs(args)

    temporada = TemporadaACB()
    ajustaInternalsTemporada(args, temporada)

    partidosEliminados = temporada.eliminaPartidos(args.partidos)

    if partidosEliminados:
        sys.setrecursionlimit(50000)
        if 'outfile' in args and args.outfile:
            temporada.grabaTemporada(args.outfile)

    for part in sorted(partidosEliminados, key=attrgetter('fechaPartido')):
        logging.info("Eliminado partido: %s. [Descargado: %s]", part, part.timestamp)


def ajustaInternalsTemporada(args, temporada):
    if 'infile' in args and args.infile:
        temporada.cargaTemporada(args.infile)


def preparaLogs(args: Namespace):
    logger = logging.getLogger()
    if args.debug:
        prepareLogger(logger=logger, level=logging.DEBUG)
    else:
        prepareLogger(logger=logger, level=logging.INFO)


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

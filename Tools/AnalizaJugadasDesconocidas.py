#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
from collections import defaultdict
from compression import zstd
from pickle import loads
from typing import Dict, TextIO

from CAPcore.Logging import prepareLogger
from CAPcore.Web import downloadPage
from configargparse import ArgumentParser, Namespace

from SMACB.PartidoACB import PartidoACB
from SMACB.TemporadaACB import cargaTemporada
from Utils.ProcessMDparts import procesaMDjugadas, play2key, jugadaTag2Desc, jugada2str, jugadaKey2sort, jugadaKey2str
from Utils.Web import extractPagDataScripts, prepareDownloading


def sacaJugadoresPartido(part: PartidoACB) -> dict:
    tradKeys = {'dorsal': 'playerNumber', 'nombre': 'playerName'}
    result = {}
    for data in part.Jugadores.values():
        auxResult = {v: data[k] for k, v in tradKeys.items()}
        result[data['codigo']] = auxResult

    return {'infoJugadores': result}


def procesaTemporada(args: Namespace) -> Dict[str, dict]:
    datosTemp = cargaTemporada(args.tempoFile)

    ListaJugadas: dict = {}

    for data in datosTemp.Partidos.values():
        auxMetadata = data.metadataEmb
        if auxMetadata is None:
            continue
        actMetadata = loads(zstd.decompress(auxMetadata))
        if 'jugadas' in actMetadata:
            auxResult = {}
            auxResult.update(actMetadata['jugadas'])
            auxURL = data.metadataEnlaces['jugadas']

            jugPartido = sacaJugadoresPartido(data)
            auxResult.update(jugPartido)
            ListaJugadas[auxURL] = auxResult

    return ListaJugadas


def procesaURL(args: Namespace) -> Dict[str, dict]:
    browser, config = prepareDownloading(None, None)
    pagJugadas = downloadPage(args.url, home=None, browser=browser, config=config)

    r1 = procesaMDjugadas(extractPagDataScripts(pagJugadas, 'initialMatchPlayByPlay'))

    result = {args.url: {"playbyplay": r1["jugadas"], "infoJugadores": r1["infoJugadores"]}}

    return result


def hayJugadasDesc(data: dict) -> bool:
    return any(play2key(play) not in jugadaTag2Desc for play in data["playByPlay"])


def vuelcaListaCompleta(url: str, data: dict, salida: TextIO):
    print(f"Listado de jugadas '{url}'\n", file=salida)
    jugadores = data['infoJugadores']
    for lnum, play in enumerate(data["playByPlay"]):
        vuelcaLineaJugada(lnum, play, jugadores, salida)


def vuelcaLineaJugada(lnum: int, play, jugadores, salida: TextIO):
    aux = {}
    aux.update(play)
    if play['codigoJug'] != 'None':
        aux.update(jugadores[play['codigoJug']])

    markJugada = " " if play2key(play) in jugadaTag2Desc else "*"
    print(f"{markJugada} l:{lnum:5} {jugada2str(aux)}", file=salida)


def jugadasDesconocidasPartido(data: dict):
    return (play2key(play) not in jugadaTag2Desc for play in data["playByPlay"])


def vuelcaListaParcial(url: str, data: dict, args: Namespace, salida: TextIO):
    context = args.context
    lineasAgrup: dict = defaultdict(lambda: {'count': 0, 'lines': []})

    for lnum in range(len(data["playByPlay"])):
        playKey = play2key(data["playByPlay"][lnum])
        if playKey in jugadaTag2Desc:
            continue
        lineasAgrup[playKey]['count'] += 1
        lineasAgrup[playKey]['lines'].append(lnum)

    print(f"Listado de jugadas no identificadas de '{url}'\n", file=salida)

    for k in sorted(lineasAgrup.keys(), key=jugadaKey2sort):
        print(f"Jugada: {jugadaKey2str(k)} [{lineasAgrup[k]['count']}]")
        for ltarg in sorted(lineasAgrup[k]['lines']):
            for lnum in range(max(0, ltarg - context), min(ltarg + 1 + context, len(data["playByPlay"]))):
                vuelcaLineaJugada(lnum, data['playByPlay'][lnum], data['infoJugadores'], salida)
            print("++++++++++")

        print("---------------------------", file=salida)

    print("\n===================================\n", file=salida)


def muestraDatos(datos: dict, args: Namespace, salida: TextIO):
    for url, data in datos.items():
        if not hayJugadasDesc(data):
            continue
        if args.all:
            print(f"URL {url} tiene jugadas desc")
            vuelcaListaCompleta(url, data, salida)
            print("\n===================================\n", file=salida)

        vuelcaListaParcial(url, data, args, salida)


def main(args: Namespace):
    outputDest = prepareOutput(args)

    datosAmostrar = procesaTemporada(args) if args.tempoFile is not None else procesaURL(args)

    muestraDatos(datosAmostrar, args, outputDest)


def preparaLogs(args: Namespace):
    logger = logging.getLogger()
    if args.debug:
        prepareLogger(logger=logger, level=logging.DEBUG)
    elif args.verbose:
        prepareLogger(logger=logger, level=logging.INFO)
    else:
        prepareLogger(logger=logger)


def prepareOutput(args: Namespace) -> TextIO:
    result = open(args.outfile, mode="w") if args.outfile is not None else sys.stdout
    return result


def parse_arguments() -> Namespace:
    parser = ArgumentParser()

    parser.add('-t', '--temporada', dest='tempoFile', type=str, action="store", required=False,
               help='Fichero de datos de temporada a analizar')
    parser.add('-u', '--url', dest='url', type=str, action="store", required=False,
               help='URL de pagina de jugadas a analizar')

    parser.add('-v', dest='verbose', action="count", required=False, help='Salida más detallada',
               default=0)
    parser.add('-d', dest='debug', action="store_true", required=False, help='Salida más detallada',
               default=False)
    parser.add('-l', '--logfile', dest='logfile', type=str, required=False,
               help="Location of logfile (defaults to stderr)")

    parser.add('-a', '--all', dest='all', action="store_true", required=False,
               help="Muestra todas las jugadas")
    parser.add('-c', '--context', dest='context', type=int, action="store", required=False, default=4,
               help="Numero de líneas a mostrar rodeando a la de interés C lineas + LI + C lineas")

    parser.add('-o', dest='outfile', type=str, help='Fichero de salida', required=False)

    args = parser.parse_args()

    if args.tempoFile is None and args.url is None:
        parser.error("Necesitas o -t/--temporada o -u/--url")
    return args


if __name__ == '__main__':
    argsCLI = parse_arguments()
    main(argsCLI)

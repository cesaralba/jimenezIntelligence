#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from time import strftime

from configargparse import ArgumentParser

from SMACB.PartidoACB import PartidoACB
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import FORMATOtimestamp


def extraeJugadoresSuperManager(datosSM):

    resultado = dict()
    maxJornada = max(datosSM.jornadas.keys())

    def listaDatos():
        return [None] * maxJornada

    def findSubKeys(data):
        resultado = defaultdict(int)

        if type(data) is not dict:
            print("Parametro pasado no es un diccionario")
            return resultado

        for clave in data:
            valor = data[clave]
            if type(valor) is not dict:
                print("Valor para '%s' no es un diccionario")
                continue
            for subclave in valor.keys():
                resultado[subclave] += 1

        return resultado

    mercadosAMirar = [None] * (maxJornada)
    # ['proxFuera', 'lesion', 'cupo', 'pos', 'foto', 'nombre', 'codJugador', 'temp', 'kiaLink', 'equipo', 'promVal',
    # 'precio', 'enEquipos%', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%', 'rival', 'CODequipo',
    # 'CODrival', 'info']
    keysJugDatos = ['lesion', 'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'CODequipo', 'CODrival']
    keysJugInfo = ['nombre', 'codJugador', 'cupo', 'pos', 'equipo', 'proxFuera', 'rival', 'activo', 'lesion',
                   'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%', 'rival',
                   'CODequipo', 'CODrival']

    for key in keysJugDatos:
        resultado[key] = defaultdict(listaDatos)
    for key in keysJugInfo + ['activo']:
        resultado['I-' + key] = dict()

    for jornada in datosSM.mercadoJornada:
        mercadosAMirar[jornada - 1] = datosSM.mercadoJornada[jornada]
    ultMercado = datosSM.mercado[datosSM.ultimoMercado]

    for i in range(len(mercadosAMirar)):
        mercadoID = mercadosAMirar[i]
        if not mercadoID:
            continue

        mercado = datosSM.mercado[mercadoID]

        for jugSM in mercado.PlayerData:
            jugadorData = mercado.PlayerData[jugSM]
            codJugador = jugadorData['codJugador']

            # print("J: ",jugadorData.keys())

            for key in jugadorData:
                if key in keysJugDatos:
                    resultado[key][codJugador][i] = jugadorData[key]
                if key in keysJugInfo:
                    resultado['I-' + key][codJugador] = jugadorData[key]

    for jugSM in resultado['lesion']:
        resultado['I-activo'][jugSM] = (jugSM in ultMercado.PlayerData)

    return(resultado)


def extraeJugadoresTemporada(temporada):
    resultado = dict()

    def MaxJornada(temporada):
        acums = defaultdict(int)
        for claveP in temporada.Partidos:
            partido = temporada.Partidos[claveP]
            acums[partido.Jornada] += 1

        return max(acums.keys())

    maxJ = MaxJornada(temporada)

    def listaDatos():
        return [None] * maxJ

    clavePartido = ['FechaHora']
    claveJugador = ['esLocal', 'titular', 'nombre', 'haGanado', 'haJugado', 'equipo', 'CODequipo', 'rival', 'CODrival']
    claveEstad = ['Segs', 'P', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'T1-C', 'T1-I', 'T1%', 'REB-T', 'R-D',
                  'R-O', 'A', 'BR', 'BP', 'C', 'TAP-F', 'TAP-C', 'M', 'FP-F', 'FP-C', '+/-', 'V']

    for clave in clavePartido + claveJugador + claveEstad:
        resultado[clave] = defaultdict(listaDatos)

    for claveP in temporada.Partidos:
        partido = temporada.Partidos[claveP]
        jornada = partido.Jornada - 1
        fechahora = partido.FechaHora

        for claveJ in partido.Jugadores:
            jugador = partido.Jugadores[claveJ]

            resultado['FechaHora'][claveJ][jornada] = fechahora

            for subClave in claveJugador:
                resultado[subClave][claveJ][jornada] = jugador[subClave]

            for subClave in claveEstad:
                if subClave in jugador['estads']:
                    resultado[subClave][claveJ][jornada] = jugador['estads'][subClave]

    return resultado


def CuentaClavesPartido(x):
    if type(x) is not dict:
        raise ValueError("CuentaClaves: necesita un diccionario")

    resultado = defaultdict(int)

    for clave in x:
        valor = x[clave]

        if type(valor) is not PartidoACB:
            print("CuentaClaves: objeto de clave '%s' no es un PartidoACB, %s" % (clave, type(valor)))
            continue

        for subclave in valor.__dict__.keys():
            resultado[subclave] += 1

    return resultado


if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)

    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

    args = parser.parse_args()

    sm = SuperManagerACB()

    if 'infile' in args and args.infile:
        sm.loadData(args.infile)
        print("Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    temporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)
        print("Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))
        print(temporada.Calendario.equipo2codigo)
        print(temporada.Calendario.codigo2equipo)

    jugSM = extraeJugadoresSuperManager(sm)
    jugTM = extraeJugadoresTemporada(temporada)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from time import strftime

from configargparse import ArgumentParser

from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import FORMATOtimestamp


def extraeJugadoresSuperManager(datosSM, temporada=None):

    print("SM:", datosSM.__dict__.keys())
    if temporada:
        print("TE: ", temporada.__dict__.keys())
        print("TE-CA: ", temporada.Calendario.__dict__.keys())
        print("TE-E2C: ", temporada.Calendario.equipo2codigo)
        print("TE-C2E: ", temporada.Calendario.codigo2equipo)

    resultado = dict()
    maxJornada = max(datosSM.jornadas.keys())

    def listaDatos():
        return [None] * maxJornada

    mercadosAMirar = [None] * (maxJornada)

    keysJugDatos = ['lesion', 'promVal', 'precio', 'valJornada', 'prom3Jornadas']
    keysJugInfo = ['nombre', 'codJugador', 'cupo', 'pos', 'equipo', 'proxFuera', 'rival', 'activo', 'lesion',
                   'promVal', 'precio', 'valJornada', 'prom3Jornadas', 'sube15%', 'seMantiene', 'baja15%']

    for key in keysJugDatos:
        resultado[key] = defaultdict(listaDatos)
    for key in keysJugInfo:
        resultado['I' + key] = dict()
    if temporada:
        resultado["CODrival"] = defaultdict(listaDatos)
        resultado["CODequipo"] = defaultdict(listaDatos)
        resultado["I-CODrival"] = dict()
        resultado["I-CODequipo"] = dict()

    for jornada in datosSM.mercadoJornada:
        mercadosAMirar[jornada - 1] = datosSM.mercadoJornada[jornada]
    ultMercado = datosSM.mercado[datosSM.ultimoMercado]

    print(mercadosAMirar)

    for i in range(len(mercadosAMirar)):
        mercadoID = mercadosAMirar[i]
        if not mercadoID:
            continue

        mercado = datosSM.mercado[mercadoID]
        print("Merc: ", mercado.__dict__.keys())

        for jugSM in mercado.PlayerData:
            jugadorData = mercado.PlayerData[jugSM]
            codJugador = jugadorData['codJugador']

            # print("J: ",jugadorData.keys())

            for key in jugadorData:
                if key in keysJugDatos:
                    resultado[key][codJugador][i] = jugadorData[key]
                if key in keysJugInfo:
                    resultado['I' + key][codJugador] = jugadorData[key]
                if temporada:
                    dato = jugadorData[key]
                    if key in ("rival", "equipo"):
                        if dato in temporada.Calendario.equipo2codigo:
                            resultado["COD" + key][codJugador][i] = temporada.Calendario.equipo2codigo[dato]
                            resultado["I-" + "COD" + key][codJugador] = temporada.Calendario.equipo2codigo[dato]
                        else:
                            print("Equipo desconocido (%s): %s" % (key, dato))

    for jugSM in resultado['lesion']:
        resultado['Iactivo'][jugSM] = (jugSM in ultMercado.PlayerData)

    print(resultado.keys())
    print(len(resultado['Icupo']))
    print(sum([1 for x in resultado['Iactivo'] if resultado['Iactivo'][x]]))

    for jugSM in resultado["CODrival"]:
        print(resultado["Inombre"][jugSM])
        print(resultado["I-CODequipo"][jugSM])
        print(resultado["Ipos"][jugSM])
        print(resultado["lesion"][jugSM])

    return(resultado)


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

    jugSM = extraeJugadoresSuperManager(sm, temporada)

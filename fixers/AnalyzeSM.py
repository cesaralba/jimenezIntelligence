#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser

# from SMACB.MercadoPage import MercadoPageContent
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB

# from Utils.Misc import ReadFile

if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-i', dest='sminfile', type=str, env_var='SM_INFILE', required=False)
    parser.add('-o', dest='smoutfile', type=str, env_var='SM_OUTFILE', required=False)
    parser.add('-t', dest='tempin', type=str, env_var='SM_TEMPIN', required=False)
    parser.add('-x', dest='tempout', type=str, env_var='SM_TEMPOUT', required=False)
    parser.add_argument(dest='files', type=str, nargs='*')

    args = parser.parse_args()

    sm = SuperManagerACB()

    if 'sminfile' in args and args.sminfile:
        sm.loadData(args.sminfile)

    temporada = None
    if 'tempin' in args and args.tempin:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.tempin)
        print(temporada.Calendario.equipo2codigo)

    print(sm.__dict__.keys())
    print("LigaID: ", sm.ligaID)
    print("Jornadas: ", sm.jornadas.keys())
    print("General: ", sm.general.keys())
    print("Broker: ", sm.broker.keys())
    print("Puntos: ", sm.puntos.keys())
    print("Rebotes: ", sm.rebotes.keys())
    print("Triples: ", sm.triples.keys())
    print("Asistencias: ", sm.asistencias.keys())
    print("Mercado: ", sm.mercado.keys())
    print("MercadoJornada: ", sm.mercadoJornada.keys())
    print("UltimoMercado: ", sm.ultimoMercado)

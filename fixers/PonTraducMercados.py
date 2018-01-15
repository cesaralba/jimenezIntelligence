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

    # Añade códigos de equipo
    mercadoKeys = list(sm.mercado.keys())
    for clave in mercadoKeys:
        mercadoClave = sm.mercado[clave]
        if hasattr(mercadoClave,'equipo2codigo'):
            print("Skipping %s" % clave)
            continue
        mercadoClave.asignaCodigosEquipos(datosACB=temporada)
        sm.mercado[clave] = mercadoClave
        sm.changed = True

        print(clave, mercadoClave, temporada.changed)
    for partidoID in temporada.Partidos:
        partido = temporada.Partidos[partidoID]
        print(partidoID, partido.DatosSuministrados)
        print(partido.Jugadores)

    print(temporada.Calendario.equipo2codigo)

    if sm.changed and ('smoutfile' in args) and args.smoutfile:
        print("There were changes!")
        sm.saveData(args.smoutfile)

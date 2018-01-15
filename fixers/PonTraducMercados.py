#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser

from SMACB.PartidoACB import OtherTeam
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
        if hasattr(mercadoClave, 'equipo2codigo'):
            print("Skipping %s" % clave)
            continue
        mercadoClave.asignaCodigosEquipos(datosACB=temporada)
        sm.mercado[clave] = mercadoClave
        sm.changed = True

        print(clave, mercadoClave, temporada.changed)

    ultimoPartido = None
    for partidoID in temporada.Partidos:
        changes = False
        partido = temporada.Partidos[partidoID]
        ultimoPartido = partidoID
        for estado in partido.Equipos:
            nuevosDatos = {'equipo': partido.EquiposCalendario[estado],
                           'CODequipo': partido.CodigosCalendario[estado],
                           'rival': partido.EquiposCalendario[OtherTeam(estado)],
                           'CODrival': partido.CodigosCalendario[OtherTeam(estado)],
                           'estado': estado, 'esLocal': (estado == "Local")}

            for jugador in partido.Equipos[estado]['Jugadores']:
                for clave in nuevosDatos:
                    if clave in partido.Jugadores[jugador]:
                        continue
                    partido.Jugadores[jugador][clave] = nuevosDatos[clave]
                    changes = True
        if changes:
            temporada.Partidos[partidoID] = partido
            temporada.changed = True
            resumenPartido = " * %s: %s (%s) %i - %i %s (%s) " % (partidoID, partido.EquiposCalendario['Local'],
                                                                  partido.CodigosCalendario['Local'],
                                                                  partido.ResultadoCalendario['Local'],
                                                                  partido.ResultadoCalendario['Visitante'],
                                                                  partido.EquiposCalendario['Visitante'],
                                                                  partido.CodigosCalendario['Visitante'])

            print(resumenPartido)

    if sm.changed and ('smoutfile' in args) and args.smoutfile:
        print("Supermanager: there were changes!")
        sm.saveData(args.smoutfile)

    if temporada.changed and ('tempout' in args) and args.tempout:
        print("Temporada: There were changes!")
        temporada.grabaTemporada(args.tempout)

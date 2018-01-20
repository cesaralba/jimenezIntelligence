#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser

from SMACB.TemporadaACB import TemporadaACB

# from Utils.Misc import ReadFile

if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-t', dest='tempin', type=str, env_var='SM_TEMPIN', required=True)
    parser.add('-x', dest='tempout', type=str, env_var='SM_TEMPOUT', required=False)
    parser.add_argument(dest='files', type=str, nargs='*')

    args = parser.parse_args()

    temporada = None
    if 'tempin' in args and args.tempin:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.tempin)

    for jornadaT in temporada.Calendario.Jornadas:
        datosJornada = temporada.Calendario.Jornadas[jornadaT]
        if datosJornada['partidos']:
            print(jornadaT, temporada.Calendario.Jornadas[jornadaT]['nombre'])

        for partidoID in datosJornada['partidos']:
            changesP = False
            datosPartido = temporada.Partidos[partidoID]

            if datosPartido.Jornada != jornadaT:
                datosPartido.Jornada = jornadaT
                changes = True

            nuevosDatos = {'competicion': datosPartido.competicion,
                           'temporada': datosPartido.temporada,
                           'jornada': datosPartido.Jornada
                           }

            for jugID in datosPartido.Jugadores:
                datosJug = datosPartido.Jugadores[jugID]
                changesJ = False

                for clave in nuevosDatos:
                    if clave in datosJug:
                        continue
                    datosJug[clave] = nuevosDatos[clave]
                    changesJ = True

                if changesJ:
                    datosPartido.Jugadores[jugID] = datosJug
                    changesP = True

            if changesP:
                temporada.changed = True
                temporada.Partidos[partidoID] = datosPartido

                print(datosPartido.resumenPartido())

    if temporada.changed and ('tempout' in args) and args.tempout:
        print("Temporada: There were changes!")
        temporada.grabaTemporada(args.tempout)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser

# from SMACB.MercadoPage import MercadoPageContent
from SMACB.TemporadaACB import TemporadaACB

# from Utils.Misc import ReadFile

if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-i', dest='tempin', type=str, env_var='SM_TEMPIN', required=False)
    parser.add('-o', dest='tempout', type=str, env_var='SM_TEMPOUT', required=False)
    parser.add_argument(dest='trads', type=str, nargs='*')

    args = parser.parse_args()

    temporada = None
    if 'tempin' in args and args.tempin:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.tempin)

    for trad in args.trads:
        try:
            newCod, newNombre = trad.split(':', maxsplit=1)
        except ValueError:
            print("AddTraducJugadores: Traducción '%s' incorrecta. Formato debe ser codigo:nombre. Ignorando" % trad)
            continue

        print("AddTraducJugadores: añadiendo '%s' -> '%s'" % (newNombre, newCod))
        temporada.nuevaTraduccionJugador(newCod, newNombre)

    if temporada.changed and ('tempout' in args) and args.tempout:
        print("Temporada: There were changes!")
        temporada.grabaTemporada(args.tempout)

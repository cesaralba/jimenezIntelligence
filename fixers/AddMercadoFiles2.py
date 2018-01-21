#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict

from configargparse import ArgumentParser

from SMACB.MercadoPage import MercadoPageContent
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import ReadFile


def cuentaFuera(mercado):
    resultado = defaultdict(int)

    for jug in mercado.PlayerData:
        resultado[mercado.PlayerData[jug]['proxFuera']] += 1

    return resultado


if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=False)
    parser.add('-j', dest='jornada', action='append', required=False)
    parser.add_argument(dest='files', type=str, nargs='*')

    args = parser.parse_args()

    sm = SuperManagerACB()

    if 'infile' in args and args.infile:
        sm.loadData(args.infile)

    temporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)

    # Carga los ficheros nuevos
    orig = None
    # print(sm.mercado.keys())
    # print(sm.mercadoJornada)
    sm.mercado = dict()
    sm.mercadoJornada = dict()
    sm.ultimoMercado = None

    for mercadoFile in args.files:

        Mfile = ReadFile(mercadoFile)
        mf = MercadoPageContent(Mfile, datosACB=temporada)
        mf.setTimestampFromStr(mf.source)

        if orig is None:
            orig = mf

            existe = False
            for existMercado in sm.mercado.values():
                if not mf != existMercado:
                    print("Mercado de fichero '%s' ya estaba en SM. Clave: %s <- %s" % (mercadoFile,
                                                                                        mf.timestampKey(),
                                                                                        existMercado.timestampKey()
                                                                                        )
                          )
                    existe = True
                    break

            if not existe:
                print("Añadido mercado de fichero '%s'. Clave: %s " % (mercadoFile, mf.timestampKey()))
                sm.addMercado(mf)
                continue

        if orig != mf:
            existe = False
            for existMercado in sm.mercado.values():
                if not mf != existMercado:
                    print("Mercado de fichero '%s' ya estaba en SM. Clave: %s <- %s" % (mercadoFile,
                                                                                        mf.timestampKey(),
                                                                                        existMercado.timestampKey()
                                                                                        )
                          )
                    existe = True
                    break

            if not existe:
                print("Añadido mercado de fichero '%s'. Clave: %s " % (mercadoFile, mf.timestampKey()))
                sm.addMercado(mf)
                orig = mf
                continue

        else:
            print("Ignorando fichero '%s'. Clave: %s" % (mercadoFile, mf.timestampKey()))

    idJornadas = [str(x) for x in sm.jornadas]
    for clave in args.jornada:
        pair = clave.split(":", 2)
        if len(pair) != 2:
            print("Clave suministrada '%s' no valida. Formato: J:ClaveMercado" % clave)
            continue

        idJor = pair[0]
        idMercado = pair[1]

        ok = True
        if (idJor not in idJornadas) and not (idJor == "0"):
            print("Clave suministrada '%s' no valida. Jornada '%s' desconocida." % (clave, idJor))
            ok = False

        if idMercado not in sm.mercado:
            print("Clave suministrada '%s' no valida. Mercado '%s' desconocido." % (clave, idMercado))
            ok = False

        if not ok:
            print("Clave suministrada '%s' con problemas. Ignorando." % clave)
            continue

        sm.mercadoJornada[int(idJor)] = idMercado
        sm.changed = True

    # Compara los ficheros registrados para detectar cambio de jornada
    orig = None
    time2jornada = dict()
    for jornada in sm.mercadoJornada:
        time2jornada[sm.mercadoJornada[jornada]] = jornada

    for merc in sorted(sm.mercado.keys()):
        mf = sm.mercado[merc]

        if orig is None:
            orig = mf
            print(" ", merc)  # ,mf
            continue

        jornada = time2jornada.get(merc, "-")
        if orig != mf:
            diffs = orig.diff(mf)

            # print(Mfile['source'], "There were changes:\n", diffs)
            if diffs.cambioJornada:
                fueras = cuentaFuera(mf)

                print("J", merc,
                      "Cambio de jornada", mf.timestampKey(),
                      "J: ", jornada, fueras)
            else:
                print("C", merc)
            # print(diffs)

        else:
            print(" ", merc)

        orig = mf

    print(sm.mercadoJornada)

    if sm.changed and ('outfile' in args) and args.outfile:
        print("There were changes!")
        sm.saveData(args.outfile)

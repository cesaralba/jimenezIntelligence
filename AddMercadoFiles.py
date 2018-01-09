#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser

from SMACB.MercadoPage import MercadoPageContent
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import ReadFile

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

    # Convierte a clave STR el ultimoMercado
    ultimoMercado = sm.ultimoMercado
    print(ultimoMercado.__dict__.keys())

    if ultimoMercado and type(ultimoMercado) is MercadoPageContent:
        if hasattr(ultimoMercado, 'NoFoto2Nombre'):
            NoFotoData = dict(zip(ultimoMercado.NoFoto2Nombre,
                                  [ultimoMercado.PlayerData[x] for x in ultimoMercado.NoFoto2Nombre]))

            ultimoMercado.arreglaNoFotos(datosACB=temporada,
                                         NoFoto2Nombre=ultimoMercado.NoFoto2Nombre,
                                         Nombre2NoFoto=ultimoMercado.Nombre2NoFoto,
                                         NoFotoData=NoFotoData)
            ultimoMercado.__delattr__('NoFoto2Nombre')
            ultimoMercado.__delattr__('Nombre2NoFoto')
            ultimoMercado.__delattr__('contadorNoFoto')
        ultimoMercadoKey = ultimoMercado.timestampKey()
        sm.ultimoMercado = None
        sm.addMercado(ultimoMercado)
        sm.ultimoMercado = ultimoMercadoKey
        sm.changed = True

    # Convierte a clave STR los mercados ya grabados en la estructura y mueve los que son de jornada a mercadoJornadas
    mercadoKeys = list(sm.mercado.keys())
    for clave in mercadoKeys:
        mercadoClave = sm.mercado[clave]
        if type(sm.mercado[clave]) is not str:
            if hasattr(mercadoClave, 'NoFoto2Nombre'):
                NoFotoData = dict(zip(mercadoClave.NoFoto2Nombre,
                                  [mercadoClave.PlayerData[x] for x in mercadoClave.NoFoto2Nombre]))

                mercadoClave.arreglaNoFotos(datosACB=temporada, NoFoto2Nombre=mercadoClave.NoFoto2Nombre,
                                            Nombre2NoFoto=mercadoClave.Nombre2NoFoto,
                                            NoFotoData=NoFotoData)
                mercadoClave.__delattr__('NoFoto2Nombre')
                mercadoClave.__delattr__('Nombre2NoFoto')
                mercadoClave.__delattr__('contadorNoFoto')

            sm.addMercado(mercadoClave)
            sm.changed = True

        if clave in sm.jornadas:
            sm.mercado.pop(clave)
            sm.mercadoJornada[clave] = mercadoClave.timestampKey()
            sm.changed = True

    # Carga los ficheros nuevos
    orig = None
    for mercadoFile in args.files:

        Mfile = ReadFile(mercadoFile)
        mf = MercadoPageContent(Mfile, datosACB=temporada)
        mf.SetTimestampFromStr(mf.source)

        if orig is None:
            orig = mf
            print("Añadido mercado de fichero '%s'. Clave: %s " % (mercadoFile, mf.timestampKey()))

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
            diffs = orig.Diff(mf)

            # print(Mfile['source'], "There were changes:\n", diffs)
            if diffs.cambioJornada:
                print("J", merc,
                      "Cambio de jornada", mf.timestampKey(),
                      "J: ", jornada)
            else:
                print("C", merc)
            # print(diffs)

        else:
            print(" ", merc)

        orig = mf

    idJornadas = [str(x) for x in sm.jornadas]
    for clave in args.jornada:
        pair = clave.split(":", 2)
        if len(pair) != 2:
            print("Clave suministrada '%s' no valida. Formato: J:ClaveMercado" % clave)
            continue

        idJor = pair[0]
        idMercado = pair[1]

        ok = True
        if idJor not in idJornadas:
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

    print(sm.mercadoJornada)

    if sm.changed and ('outfile' in args) and args.outfile:
        print("There were changes!")
        sm.saveData(args.outfile)

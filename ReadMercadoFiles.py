#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse

from _collections import defaultdict
from SMACB.MercadoPage import MercadoPageContent
from Utils.Misc import ReadFile


def cuentaFuera(mercado):
    resultado = defaultdict(int)

    for jug in mercado.PlayerData:
        resultado[mercado.PlayerData[jug]['proxFuera']] += 1

    return resultado


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(dest='files', type=str, nargs='+')
    # parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()

    files = []

    for x in args.files:
        files.append(ReadFile(x))

    orig = None

    for Mfile in files:
        mf = MercadoPageContent(Mfile)
        mf.setTimestampFromStr(mf.source)
        print(cuentaFuera(mf))

        if orig is None:
            orig = mf
            print(" ", Mfile['source'])  # ,mf
            continue

        diffs = orig.diff(mf)

        if orig != mf:

            # print(Mfile['source'], "There were changes:\n", diffs)
            if diffs.cambioJornada:
                print("J", Mfile['source'],
                      "Cambio de jornada", mf.timestampKey(),
                      "Len newRivals", len(diffs.newRivals),
                      "teamsJornada", diffs.teamsJornada)
            else:
                print("C", Mfile['source'],
                      "Len newRivals", len(diffs.newRivals),
                      "teamsJornada", diffs.teamsJornada)
            # print(diffs)

        else:
            print(" ", Mfile['source'])  # ,mf
            # print(Mfile['source'], "Nodiffs") #,mf)
            pass

        orig = mf

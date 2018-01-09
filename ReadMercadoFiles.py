#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse

from SMACB.MercadoPage import MercadoPageContent
from Utils.Misc import ReadFile

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
        mf.SetTimestampFromStr(mf.source)

        if orig is None:
            orig = mf
            print(" ", Mfile['source'])  # ,mf
            continue

        diffs = orig.Diff(mf)

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

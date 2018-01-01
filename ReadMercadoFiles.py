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
            continue

        diffs = orig.Diff(mf)

        if orig != mf:

            print(Mfile['source'], "There were changes:\n", diffs)  # ,mf
            pass

        else:
            # print(Mfile['source'], "Nodiffs") #,mf)
            pass

        orig = mf

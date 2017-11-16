# -*- coding: utf-8 -*-
#!/usr/bin/env python3

import argparse
from SMACB.MercadoPage import MercadoPageContent

#from re import sub
#from sys import exit
#from time import strptime,strftime

def ReadMercadoFile(filename):
    with open(filename,"r") as handin:
        read_data= handin.read()
    return { 'source': filename, 'data': ''.join(read_data)}





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(dest='files', type=str,nargs='+')
    #parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()

    files=[]

    for x in args.files:
        files.append(ReadMercadoFile(x))

    orig=None


    for Mfile in files:
        mf=MercadoPageContent(Mfile)

        if orig is None:
            orig = mf
            next

        orig.Compare(mf)
        #print(mf.source,mf.PositionsCounter)

        orig = mf






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

    print(args)

    files=[]

    for x in args.files:
        print(x)
        files.append(ReadMercadoFile(x))


    for Mfile in files:
        mf=MercadoPageContent(Mfile)
        print(mf.source,mf.PositionsCounter)






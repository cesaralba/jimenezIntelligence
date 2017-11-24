# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from configargparse import ArgumentParser
from SMACB.EstadisticasACB import CalendarioACB

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)
    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

    # parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()

    cal = CalendarioACB(config=args)
    cal.BajaCalendario()

#     if 'infile' in args and args.infile:
#         sm.loadData(args.infile)
#
#     #sm = SuperManagerACB(config=args)
#     sm.Connect()
#
#     sm.getSMstatus()
#
#     if sm.changed and ('outfile' in args and args.outfile):
#         print("There were changes!")
#         sm.saveData(args.outfile)



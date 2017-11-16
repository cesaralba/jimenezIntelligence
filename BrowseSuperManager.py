# -*- coding: utf-8 -*-
#!/usr/bin/env python3
from configargparse import ArgumentParser
from SMACB.SuperManager import SuperManagerACB

# from SMACB.MercadoPage import MercadoPageContent
if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add('-u', dest='user', type=str, env_var='SM_USER', required=True)
    parser.add('-p', dest='password', type=str, env_var='SM_PASSWORD', required=True)
    parser.add('-l', dest='league', type=str, env_var='SM_LEAGUE', required=False)
    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)
    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=False)
    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

    # parser.add_argument('-i', '--input', type=str, required=False, dest='infile')

    args = parser.parse_args()

    sm = SuperManagerACB(config=args)

    if 'infile' in args and args.infile:
        sm.loadData(args.infile)

    #sm = SuperManagerACB(config=args)
    sm.Connect()
    print(sm)

    sm.getSMstatus()

    if 'outfile' in args and args.outfile:
        sm.saveData(args.outfile)

    print(sm.asistencias,sm.broker,sm.general,sm.jornadas,sm.puntos,sm.rebotes,sm.triples)
    # sm.getIntoPrivateLeague()

    # print(sm.browser.get_current_page())


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from itertools import product
from time import asctime, strftime

from configargparse import ArgumentParser
from joblib import Parallel, delayed

from SMACB.Guesser import (GeneraCombinacionJugs, agregaJugadores,
                           getPlayersByPosAndCupoJornada)
from SMACB.SMconstants import CUPOS, POSICIONES
from SMACB.SuperManager import ResultadosJornadas, SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.CombinacionesConCupos import GeneraCombinaciones, calculaClaveComb
from Utils.combinatorics import n_choose_m, prod
from Utils.Misc import FORMATOtimestamp

NJOBS = 3
CLAVEPRINC = 'asistencias'
CLAVESEC = 'triples'
CLAVETERC = 'rebotes'
CLAVECUAT = 'puntos'
CLAVEQUIN = 'valJornada'
CLAVESEX = 'broker'

SEQCLAVES = ['asistencias', 'triples', 'rebotes', 'puntos']


def listaPosiciones():
    return [None] * 9


def procesaArgumentos():
    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)
    parser.add('-j', dest='jornada', type=int, required=True)

    args = parser.parse_args()

    return args


def validateCombs(comb, cuentaGrupos, resultadosSM, jugadores):
    result = defaultdict(list)
    contStats = defaultdict(lambda: defaultdict(int))

    valoresPRINC = resultadosSM.valoresSM()[CLAVEPRINC]
    valoresSEC = resultadosSM.valoresSM()[CLAVESEC]
    valoresTERC = resultadosSM.valoresSM()[CLAVETERC]
    valoresCUAT = resultadosSM.valoresSM()[CLAVECUAT]
    valoresQUIN = resultadosSM.valoresSM()[CLAVEQUIN]
    valoresSEX = resultadosSM.valoresSM()[CLAVESEX]

    teamsRES = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))))

    for t in resultadosSM.resultados:
        teamsRES[resultadosSM.resultados[t][CLAVEPRINC]][resultadosSM.resultados[t][CLAVESEC]][
            resultadosSM.resultados[t][CLAVETERC]][resultadosSM.resultados[t][CLAVECUAT]][
            resultadosSM.resultados[t][CLAVEQUIN]][resultadosSM.resultados[t][CLAVESEX]].append(t)

    grToTest = {p: cuentaGrupos[p][x] for p, x in zip(POSICIONES, comb)}
    # print(grToTest)
    prSets = prod([x['contSets'][0] for x in grToTest.values()])
    prOrig = prod([x['numCombs'] for x in grToTest.values()])
    remainers = 0

    if prSets == 0:
        print(grToTest)
        exit(1)
    print(asctime(), comb, "IN ", prOrig, prSets)

    # ['cont', 'comb', 'numCombs', 'indexes', 'pos', 'key', 'contSets', 'valSets', 'combJugs']
    combVals = [grToTest[x]['valSets'] for x in POSICIONES]
    contStats['PRI']['Ini'] += prod([len(x) for x in combVals])

    for prPRINC in product(*combVals):
        sumPRINC = sum(prPRINC)

        if sumPRINC not in valoresPRINC:
            contStats['PRI']['Nok'] += 1
            continue

        secCombsToTest = [grToTest[p]['valSets'][x] for x, p in zip(prPRINC, POSICIONES)]
        prSets += prod([len(x) for x in secCombsToTest])
        contStats['SEC']['Ini'] += prod([len(x) for x in secCombsToTest])

        for prSEC in product(*secCombsToTest):
            sumSEC = sum(prSEC)
            if sumSEC not in valoresSEC:
                contStats['SEC']['Nok'] += 1
                continue
            teamsToCheck = teamsRES[sumPRINC][sumSEC]

            if not teamsToCheck:
                contStats['SEC']['Nok'] += 1
                continue

            terCombsToTest = [se[x] for x, se in zip(prSEC, secCombsToTest)]
            prSets += prod([len(x) for x in terCombsToTest])
            contStats['TER']['Ini'] += prod([len(x) for x in terCombsToTest])

            for prTERC in product(*terCombsToTest):
                sumTERC = sum(prTERC)
                if sumTERC not in valoresTERC:
                    contStats['TER']['Nok'] += 1
                    continue
                teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC]

                if not teamsToCheck:
                    contStats['TER']['Nok'] += 1
                    continue

                cuatCombsToTest = [se[x] for x, se in zip(prTERC, terCombsToTest)]
                prSets += prod([len(x) for x in cuatCombsToTest])
                contStats['CUA']['Ini'] += prod([len(x) for x in cuatCombsToTest])

                for prCUAT in product(*cuatCombsToTest):
                    sumCUAT = sum(prCUAT)
                    if sumCUAT not in valoresCUAT:
                        contStats['CUA']['Nok'] += 1
                        continue
                    teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT]

                    if not teamsToCheck:
                        contStats['CUA']['Nok'] += 1
                        continue

                    quinCombsToTest = [se[x] for x, se in zip(prCUAT, cuatCombsToTest)]
                    prSets += prod([len(x) for x in quinCombsToTest])
                    contStats['QUIN']['Ini'] += prod([len(x) for x in quinCombsToTest])

                    for prQUIN in product(*quinCombsToTest):
                        sumQUIN = sum(prQUIN)
                        if sumQUIN not in valoresQUIN:
                            contStats['QUIN']['Nok'] += 1
                            continue
                        teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT][sumQUIN]

                        if not teamsToCheck:
                            contStats['QUIN']['Nok'] += 1
                            continue

                        sexCombsToTest = [se[x] for x, se in zip(prQUIN, quinCombsToTest)]
                        prSets += prod([len(x) for x in sexCombsToTest])
                        contStats['SEX']['Ini'] += prod([len(x) for x in sexCombsToTest])

                        for prSEX in product(*sexCombsToTest):
                            sumSEX = sum(prSEX)
                            if sumSEX not in valoresSEX:
                                contStats['SEX']['Nok'] += 1
                                continue
                            teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT][sumQUIN][sumSEX]

                            if not teamsToCheck:
                                contStats['SEX']['Nok'] += 1
                                continue

                            finCombsToTest = [se[x] for x, se in zip(prSEX, sexCombsToTest)]
                            remainers += prod([len(x) for x in finCombsToTest])
                            sol = list(zip(POSICIONES, comb, prPRINC, prSEC, prTERC, prCUAT, prQUIN, prSEX,
                                           [len(x) for x in finCombsToTest]))
                            # continue
                            # print(asctime(), comb, "MID remainers", [len(x) for x in finCombsToTest])
                            for t in teamsToCheck:
                                print("Si!", comb, t, sol)
                                result[t].append(sol)

                            continue

                            for prFin in product(*finCombsToTest):
                                jugList = prFin[0].split("-") + prFin[1].split("-") + prFin[2].split("-")
                                agr = agregaJugadores(jugList, jugadores)
                                for t in teamsToCheck:
                                    if resultadosSM.comparaAgregado(t, agr):
                                        print("Si!", comb, jugList)
                                        result[t].append(jugList)

    # print(asctime(), comb, "OUT", prOrig, prSets, len(result), {x:len(result[x]) for x in result})
    print(asctime(), comb, "OUT", prOrig, prSets, prOrig / prSets, remainers,
          contStats, )  # {x:result[x] for x in result}
    return result


if __name__ == '__main__':
    args = procesaArgumentos()

    # Carga datos
    sm = SuperManagerACB()
    if 'infile' in args and args.infile:
        sm.loadData(args.infile)
        print("Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    temporada = None
    resultadoTemporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)
        resultadoTemporada = temporada.extraeDatosJugadores()
        print("Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))

    badTeams = []

    # Recupera resultados de la jornada
    resJornada = ResultadosJornadas(args.jornada, sm, excludelist=badTeams)
    # print(resJornada.__dict__) ; exit(1)
    # Valores de los resultados de la jornada
    # puntosSM = resJornada.valoresSM()

    # Recupera los datos de los jugadores que han participado en la jornada
    indexes, posYcupos, jugadores = getPlayersByPosAndCupoJornada(args.jornada, sm, temporada)

    validCombs = GeneraCombinaciones()
    # Combinaciones con solución en J2
    # validCombs = [[0, 0, 3, 0, 2, 2, 0, 2, 2], [0, 0, 3, 0, 2, 2, 0, 3, 1], [0, 0, 3, 0, 2, 2, 1, 2, 1],
    #               [0, 0, 3, 0, 3, 1, 0, 2, 2], [0, 0, 3, 0, 3, 1, 1, 2, 1], [0, 0, 3, 1, 1, 2, 0, 3, 1]]
    groupedCombs = []
    cuentaGrupos = defaultdict(dict)
    lenPosCupos = [0] * 9
    maxPosCupos = [0] * 9
    numCombsPosYCupos = [[]] * 9
    combsPosYCupos = [[]] * 9

    for i in posYcupos:
        lenPosCupos[i] = len(posYcupos[i])
        maxPosCupos[i] = max([x[i] for x in validCombs])
        numCombsPosYCupos[i] = [0] * (maxPosCupos[i] + 1)
        combsPosYCupos[i] = [None] * (maxPosCupos[i] + 1)

        for n in range(maxPosCupos[i] + 1):
            numCombsPosYCupos[i][n] = n_choose_m(lenPosCupos[i], n)

    # Distribuciones de jugadores válidas por posición y cupo
    for c in validCombs:
        newComb = []
        for p in POSICIONES:
            indexGrupo = [indexes[p][x] for x in CUPOS]
            grupoComb = [c[i] for i in indexGrupo]
            claveComb = calculaClaveComb(grupoComb)
            if claveComb not in cuentaGrupos[p]:
                numCombs = prod([numCombsPosYCupos[x[0]][x[1]] for x in zip(indexGrupo, grupoComb)])
                cuentaGrupos[p][claveComb] = {'cont': 0, 'comb': grupoComb, 'numCombs': numCombs, 'indexes': indexGrupo,
                                              'pos': p, 'key': claveComb}
            cuentaGrupos[p][claveComb]['cont'] += 1
            newComb.append(claveComb)
        groupedCombs.append(newComb)

    print(asctime(), len(groupedCombs), len(jugadores))

    for p in cuentaGrupos:
        print(p, len(cuentaGrupos[p]))
        for c in cuentaGrupos[p]:
            print("   ", c, cuentaGrupos[p][c])
        print(sum([cuentaGrupos[p][x]['numCombs'] for x in cuentaGrupos[p]]))

    for p in POSICIONES:
        for comb in cuentaGrupos[p]:
            combList = []
            print(asctime(), p, comb, cuentaGrupos[p][comb])
            combGroup = cuentaGrupos[p][comb]['comb']
            index = cuentaGrupos[p][comb]['indexes']
            for i, n in zip(index, combGroup):
                # Genera combinaciones y las cachea
                if combsPosYCupos[i][n] is None:
                    combsPosYCupos[i][n] = GeneraCombinacionJugs(posYcupos[i], n)
                if n != 0:
                    combList.append(combsPosYCupos[i][n])

            listFin = []
            for pr in product(*combList):
                aux = []
                for gr in pr:
                    for j in gr:
                        aux.append(j)
                listFin.append(aux)
            # cuentaGrupos[p][comb]['combJugs'] = listFin
            # TODO: cuentaGrupos[p][comb]['setVals'] = set()

            colSets = dict()
            for c in listFin:
                agr = agregaJugadores(c, jugadores)
                claveJugs = "-".join(c)
                if agr[CLAVEPRINC] not in colSets:
                    colSets[agr[CLAVEPRINC]] = dict()
                if agr[CLAVESEC] not in colSets[agr[CLAVEPRINC]]:
                    colSets[agr[CLAVEPRINC]][agr[CLAVESEC]] = dict()
                if agr[CLAVETERC] not in colSets[agr[CLAVEPRINC]][agr[CLAVESEC]]:
                    colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]] = dict()
                if agr[CLAVECUAT] not in colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]]:
                    colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]] = dict()
                if agr[CLAVEQUIN] not in colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]]:
                    colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]][
                        agr[CLAVEQUIN]] = defaultdict(list)

                colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]][agr[CLAVEQUIN]][
                    agr[CLAVESEX]].append(claveJugs)

            cuentaGrupos[p][comb]['contSets'] = (len(colSets), max([len(x) for x in colSets.values()]))
            print(asctime(), p, comb, cuentaGrupos[p][comb])

            cuentaGrupos[p][comb]['valSets'] = colSets
            cuentaGrupos[p][comb]['combJugs'] = listFin

    acumSets = 0
    acumOrig = 0
    combMatchesVal = defaultdict(list)

    subSet = groupedCombs[0:100]
    subSet = groupedCombs[0:4]
    subSet = groupedCombs[0:2]
    subset = [['0-0-3', '0-2-2', '0-3-1']]

    result = Parallel(n_jobs=NJOBS)(
        delayed(validateCombs)(c, cuentaGrupos, resJornada, jugadores) for c in groupedCombs)

    # for c in groupedCombs:
    #     # print(c)
    #     grToTest = {p: cuentaGrupos[p][x] for p, x in zip(POSICIONES, c)}
    #     # print(grToTest)
    #     prSets = prod([x['contSets'][0] for x in grToTest.values()])
    #     acumSets += prSets
    #     prOrig = prod([x['numCombs'] for x in grToTest.values()])
    #     acumOrig += prOrig
    #     if prSets == 0:
    #         print(grToTest)
    #         exit(1)
    #     print(asctime(), c, prOrig, prSets)
    #
    #     # ['cont', 'comb', 'numCombs', 'indexes', 'pos', 'key', 'contSets', 'valSets', 'combJugs']
    #     combVals = [list(grToTest[x]['valSets'].keys()) for x in POSICIONES]
    #     for pr in product(*combVals):
    #         sumPR = sum(pr)
    #         if sumPR in puntosSM['valJornada']:
    #             vComb = [{'valJornada': x, 'pos': grToTest[p]['pos'], 'key': grToTest[p]['key']} for x, p in
    #                      zip(pr, POSICIONES)]
    #             combVals[sumPR].append(vComb)
    #             print("!", sumPR, vComb)
    #
    #

    print(result)
    print(acumOrig, acumSets)

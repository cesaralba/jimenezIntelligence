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
from Utils.Misc import FORMATOtimestamp, deepDict, deepDictSet

NJOBS = 2

SEQCLAVES = ['asistencias', 'triples', 'rebotes', 'puntos', 'valJornada', 'broker']


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


def validateCombs(comb, cuentaGrupos, resultadosSM):
    result = []

    print(asctime(), comb, "IN ")

    teamsRES = resultadosSM.resultados

    grToTest = {p: cuentaGrupos[p][x] for p, x in zip(POSICIONES, comb)}

    teamsOk = list(teamsRES.keys())
    claves = SEQCLAVES.copy()

    combVals = [grToTest[p]['valSets'] for p in POSICIONES]

    def ValidaCombinacion(arbolSols, claves, listaSupervivientes, resEquipos, curSol):
        if len(claves) == 0:
            return

        claveAct = claves[0]

        valoresOK = {resEquipos[e][claveAct] for e in listaSupervivientes}

        for prodKey in product(*arbolSols):
            sumKey = sum(prodKey)

            if sumKey not in valoresOK:
                # print("NO ",claveAct, prodKey,sumKey, valoresOK, curSol)
                continue

            # print("SI ",claveAct, prodKey,sumKey, valoresOK, curSol)
            nuevosSuperv = [t for t in resEquipos if resEquipos[t][claveAct] == sumKey]
            nuevosCombVals = [c[v] for c, v in zip(arbolSols, prodKey)]

            # print("SI ",claveAct, prodKey,sumKey, valoresOK, curSol)

            if len(claves) == 1:
                nuevaSol = curSol + [prodKey]
                valsSol = zip(*nuevaSol)
                dictSol = dict(zip(comb, valsSol))
                regSol = (nuevosSuperv, dictSol, prod([x for x in nuevosCombVals]))
                result.append(regSol)
                print(asctime(), "Sol", nuevosSuperv, regSol)
                continue
            else:
                deeperSol = curSol + [prodKey]
                deeper = ValidaCombinacion(nuevosCombVals, claves[1:], nuevosSuperv, resEquipos, deeperSol)
                if deeper is None:
                    continue

    ValidaCombinacion(combVals, claves, teamsOk, teamsRES, [])

    print(asctime(), comb, "OUT", len(result))

    return result

    # print(asctime(), comb, "IN ")
    #
    # # ['cont', 'comb', 'numCombs', 'indexes', 'pos', 'key', 'contSets', 'valSets', 'combJugs']
    #
    # contStats['PRI']['Ini'] += prod([len(x) for x in combVals])
    #
    # for prPRINC in product(*combVals):
    #     sumPRINC = sum(prPRINC)
    #
    #     if sumPRINC not in valoresPRINC:
    #         contStats['PRI']['Nok'] += 1
    #         continue
    #
    #     secCombsToTest = [grToTest[p]['valSets'][x] for x, p in zip(prPRINC, POSICIONES)]
    #     prSets += prod([len(x) for x in secCombsToTest])
    #     contStats['SEC']['Ini'] += prod([len(x) for x in secCombsToTest])
    #
    #     for prSEC in product(*secCombsToTest):
    #         sumSEC = sum(prSEC)
    #         if sumSEC not in valoresSEC:
    #             contStats['SEC']['Nok'] += 1
    #             continue
    #         teamsToCheck = teamsRES[sumPRINC][sumSEC]
    #
    #         if not teamsToCheck:
    #             contStats['SEC']['Nok'] += 1
    #             continue
    #
    #         terCombsToTest = [se[x] for x, se in zip(prSEC, secCombsToTest)]
    #         prSets += prod([len(x) for x in terCombsToTest])
    #         contStats['TER']['Ini'] += prod([len(x) for x in terCombsToTest])
    #
    #         for prTERC in product(*terCombsToTest):
    #             sumTERC = sum(prTERC)
    #             if sumTERC not in valoresTERC:
    #                 contStats['TER']['Nok'] += 1
    #                 continue
    #             teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC]
    #
    #             if not teamsToCheck:
    #                 contStats['TER']['Nok'] += 1
    #                 continue
    #
    #             cuatCombsToTest = [se[x] for x, se in zip(prTERC, terCombsToTest)]
    #             prSets += prod([len(x) for x in cuatCombsToTest])
    #             contStats['CUA']['Ini'] += prod([len(x) for x in cuatCombsToTest])
    #
    #             for prCUAT in product(*cuatCombsToTest):
    #                 sumCUAT = sum(prCUAT)
    #                 if sumCUAT not in valoresCUAT:
    #                     contStats['CUA']['Nok'] += 1
    #                     continue
    #                 teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT]
    #
    #                 if not teamsToCheck:
    #                     contStats['CUA']['Nok'] += 1
    #                     continue
    #
    #                 quinCombsToTest = [se[x] for x, se in zip(prCUAT, cuatCombsToTest)]
    #                 prSets += prod([len(x) for x in quinCombsToTest])
    #                 contStats['QUIN']['Ini'] += prod([len(x) for x in quinCombsToTest])
    #
    #                 for prQUIN in product(*quinCombsToTest):
    #                     sumQUIN = sum(prQUIN)
    #                     if sumQUIN not in valoresQUIN:
    #                         contStats['QUIN']['Nok'] += 1
    #                         continue
    #                     teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT][sumQUIN]
    #
    #                     if not teamsToCheck:
    #                         contStats['QUIN']['Nok'] += 1
    #                         continue
    #
    #                     sexCombsToTest = [se[x] for x, se in zip(prQUIN, quinCombsToTest)]
    #                     prSets += prod([len(x) for x in sexCombsToTest])
    #                     contStats['SEX']['Ini'] += prod([len(x) for x in sexCombsToTest])
    #
    #                     for prSEX in product(*sexCombsToTest):
    #                         sumSEX = sum(prSEX)
    #                         if sumSEX not in valoresSEX:
    #                             contStats['SEX']['Nok'] += 1
    #                             continue
    #                         teamsToCheck = teamsRES[sumPRINC][sumSEC][sumTERC][sumCUAT][sumQUIN][sumSEX]
    #
    #                         if not teamsToCheck:
    #                             contStats['SEX']['Nok'] += 1
    #                             continue
    #
    #                         finCombsToTest = [se[x] for x, se in zip(prSEX, sexCombsToTest)]
    #                         remainers += prod([len(x) for x in finCombsToTest])
    #                         sol = list(zip(POSICIONES, comb, prPRINC, prSEC, prTERC, prCUAT, prQUIN, prSEX,
    #                                        [len(x) for x in finCombsToTest]))
    #                         # continue
    #                         # print(asctime(), comb, "MID remainers", [len(x) for x in finCombsToTest])
    #                         for t in teamsToCheck:
    #                             print("Si!", comb, t, sol)
    #                             result[t].append(sol)
    #
    #                         continue
    #
    #                         for prFin in product(*finCombsToTest):
    #                             jugList = prFin[0].split("-") + prFin[1].split("-") + prFin[2].split("-")
    #                             agr = agregaJugadores(jugList, jugadores)
    #                             for t in teamsToCheck:
    #                                 if resultadosSM.comparaAgregado(t, agr):
    #                                     print("Si!", comb, jugList)
    #                                     result[t].append(jugList)
    #
    # # print(asctime(), comb, "OUT", prOrig, prSets, len(result), {x:len(result[x]) for x in result})
    # print(asctime(), comb, "OUT", prOrig, prSets, prOrig / prSets, remainers,
    #       contStats, )  # {x:result[x] for x in result}
    # return result


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
    indexes, posYcupos, jugadores, lenPosCupos = getPlayersByPosAndCupoJornada(args.jornada, sm, temporada)

    validCombs = GeneraCombinaciones()
    # Combinaciones con solución en J2
    # validCombs = [[0, 0, 3, 0, 2, 2, 0, 2, 2], [0, 0, 3, 0, 2, 2, 0, 3, 1], [0, 0, 3, 0, 2, 2, 1, 2, 1],
    #               [0, 0, 3, 0, 3, 1, 0, 2, 2], [0, 0, 3, 0, 3, 1, 1, 2, 1], [0, 0, 3, 1, 1, 2, 0, 3, 1]]
    groupedCombs = []
    cuentaGrupos = defaultdict(dict)
    maxPosCupos = [0] * 9
    numCombsPosYCupos = [[]] * 9
    combsPosYCupos = [[]] * 9

    for i in posYcupos:
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

            colSets = dict()
            for pr in product(*combList):
                aux = []
                for gr in pr:
                    for j in gr:
                        aux.append(j)

                agr = agregaJugadores(aux, jugadores)
                claveJugs = "-".join(c)
                indexComb = [agr[k] for k in SEQCLAVES]

            # cuentaGrupos[p][comb]['combJugs'] = listFin
            # TODO: cuentaGrupos[p][comb]['setVals'] = set()

                deepDictSet(colSets, indexComb, deepDict(colSets, indexComb, int) + 1)

            cuentaGrupos[p][comb]['contSets'] = (len(colSets), max([len(x) for x in colSets.values()]))
            print(asctime(), p, comb, cuentaGrupos[p][comb])

            cuentaGrupos[p][comb]['valSets'] = colSets
            # print(colSets)

            # TODO: Escribir las combinaciones de jug + agr en algún sitio para poder hacer la recomb final

    acumSets = 0
    acumOrig = 0
    combMatchesVal = defaultdict(list)

    subSet = groupedCombs[0:100]
    subSet = groupedCombs[0:4]
    subSet = groupedCombs[0:2]
    subset = [['0-0-3', '0-2-2', '0-3-1']]

    result = Parallel(n_jobs=NJOBS)(
        delayed(validateCombs)(c, cuentaGrupos, resJornada) for c in groupedCombs)

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

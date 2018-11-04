#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from itertools import product
from time import asctime, strftime, time

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

# Planes con solucion usuario    Pabmm, J5
pabloPlans = [[0, 0, 3, 1, 2, 1, 1, 2, 1],
              [0, 0, 3, 2, 1, 1, 0, 3, 1],
              [0, 1, 2, 0, 1, 3, 1, 2, 1],
              [0, 1, 2, 0, 2, 2, 0, 1, 3],
              [0, 1, 2, 0, 2, 2, 1, 2, 1],
              [0, 1, 2, 0, 2, 2, 1, 1, 2],
              [0, 1, 2, 0, 3, 1, 0, 0, 4],
              [0, 1, 2, 0, 3, 1, 0, 2, 2],
              [0, 1, 2, 0, 3, 1, 1, 1, 2],
              [0, 1, 2, 0, 3, 1, 2, 2, 0],
              [0, 1, 2, 1, 1, 2, 0, 2, 2],
              [0, 1, 2, 1, 1, 2, 1, 2, 1],
              [0, 1, 2, 1, 2, 1, 0, 1, 3],
              [0, 1, 2, 1, 2, 1, 1, 1, 2],
              [0, 1, 2, 1, 3, 0, 0, 2, 2],
              [0, 1, 2, 2, 1, 1, 0, 2, 2],
              [0, 2, 1, 0, 2, 2, 0, 2, 2],
              [0, 2, 1, 0, 2, 2, 1, 1, 2],
              [0, 2, 1, 1, 0, 3, 1, 2, 1],
              [0, 2, 1, 1, 1, 2, 0, 1, 3],
              [0, 2, 1, 1, 1, 2, 1, 1, 2],
              [0, 2, 1, 2, 1, 1, 0, 1, 3],
              [0, 2, 1, 2, 1, 1, 0, 2, 2],
              [0, 3, 0, 1, 1, 2, 0, 4, 0],
              [1, 0, 2, 0, 2, 2, 1, 2, 1],
              [1, 0, 2, 0, 3, 1, 1, 2, 1],
              [1, 0, 2, 0, 3, 1, 1, 3, 0],
              [1, 0, 2, 1, 2, 1, 0, 3, 1],
              [1, 1, 1, 0, 1, 3, 0, 3, 1],
              [1, 1, 1, 0, 1, 3, 1, 2, 1],
              [1, 1, 1, 0, 2, 2, 0, 2, 2],
              [1, 1, 1, 0, 2, 2, 1, 1, 2],
              [1, 1, 1, 0, 3, 1, 1, 1, 2],
              [1, 1, 1, 1, 1, 2, 0, 2, 2],
              [1, 1, 1, 1, 2, 1, 0, 1, 3],
              [1, 1, 1, 1, 2, 1, 0, 2, 2],
              [1, 2, 0, 1, 2, 1, 0, 1, 3]]
pabloPlans = pabloPlans[0:1]


def solucion2clave(clave, sol):
    formatos = {'asistencias': "%03d", 'triples': "%03d", 'rebotes': "%03d", 'puntos': "%03d", 'valJornada': "%05.2f",
                'broker': "%010d"}
    formatoTotal = "#".join([formatos[k] for k in SEQCLAVES])
    valores = [sol[k] for k in SEQCLAVES]
    print(formatoTotal, valores)
    return clave + "#" + (formatoTotal % tuple(valores))


def listaPosiciones():
    return [None] * 9


def procesaArgumentos():
    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)
    parser.add('-j', dest='jornada', type=int, required=True)

    parser.add('-s', '--include-socio', dest='socioIn', type=str, action="append")
    parser.add('-e', '--exclude-socio', dest='socioOut', type=str, action="append")

    parser.add('-l', '--lista-socios', dest='listaSocios', action="store_true", default=False)

    args = parser.parse_args()

    return args


def validateCombs(comb, cuentaGrupos, resultadosSM, equipo):
    result = []

    resEQ = resultadosSM.resultados[equipo]
    contExcl = {'in': 0, 'out': 0}
    grToTest = {p: cuentaGrupos[p][x] for p, x in zip(POSICIONES, comb)}

    claves = SEQCLAVES.copy()

    combVals = [grToTest[p]['valSets'] for p in POSICIONES]
    combInt = [grToTest[p]['comb'] for p in POSICIONES]

    def ValidaCombinacion(arbolSols, claves, val2match, curSol):
        if len(claves) == 0:
            return

        claveAct = claves[0]

        for prodKey in product(*arbolSols):
            sumKey = sum(prodKey)

            if sumKey != val2match[claveAct]:
                contExcl['out'] += 1
                continue

            contExcl['in'] += 1

            nuevosCombVals = [c[v] for c, v in zip(arbolSols, prodKey)]

            if len(claves) == 1:
                nuevaSol = curSol + [prodKey]
                valsSolD = [dict(zip(SEQCLAVES, s)) for s in list(zip(*nuevaSol))]
                solClaves = [solucion2clave(c, s) for c, s in zip(comb, valsSolD)]

                regSol = (equipo, solClaves, prod([x for x in nuevosCombVals]))
                result.append(regSol)
                print(asctime(), equipo, combInt, "Sol", regSol)
                continue
            else:
                deeperSol = curSol + [prodKey]
                deeper = ValidaCombinacion(nuevosCombVals, claves[1:], val2match, deeperSol)
                if deeper is None:
                    continue
        return None

    numCombs = prod([grToTest[p]['numCombs'] for p in POSICIONES])
    print(asctime(), equipo, combInt, "IN  ", numCombs)
    timeIn = time()
    ValidaCombinacion(combVals, claves, resEQ, [])
    timeOut = time()
    durac = timeOut - timeIn

    numEqs = sum([eq[-1] for eq in result])
    ops = contExcl['in'] + contExcl['out']
    descIn = contExcl['in']
    descOut = contExcl['out']

    print(asctime(), equipo, combInt, "OUT %3d %3d %10.6f %.6f%% %d -> %8d (%d,%d)" % (
        len(result), numEqs, durac, (100.0 * float(ops) / float(numCombs)), numCombs, ops, descIn, descOut), contExcl)

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

    badTeams = args.socioOut if args.socioOut is not None else []

    # Recupera resultados de la jornada
    resJornada = ResultadosJornadas(args.jornada, sm)
    goodTeams = args.socioIn if ('socioIn' in args and args.socioIn is not None) else resJornada.listaSocios()

    if args.listaSocios:
        for s in resJornada.socio2equipo:
            pref = "  "
            if s in goodTeams:
                pref = "SI"
            else:
                pref = "NO"

            if s in badTeams:
                pref = "NO"

            print("[%s] %s -> '%s'" % (pref, s, resJornada.socio2equipo[s]))

        exit(0)

    indexes, posYcupos, jugadores, lenPosCupos = getPlayersByPosAndCupoJornada(args.jornada, sm, temporada)

    validCombs = GeneraCombinaciones()
    # validCombs = pabloPlans

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
            claveComb = p + "-" + calculaClaveComb(grupoComb)
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

    resultado = defaultdict(list)

    for s in goodTeams:
        if s in badTeams:
            continue

        result = Parallel(n_jobs=NJOBS, verbose=40)(
            delayed(validateCombs)(c, cuentaGrupos, resJornada, s) for c in groupedCombs)

        resultado[s] = result

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

    print(resultado)
    # print(acumOrig, acumSets)

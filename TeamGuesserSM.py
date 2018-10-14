#!/usr/bin/env python3
# -*- coding: utf-8 -*-

CLAVEPRINC = 'asistencias'
CLAVESEC =  'puntos'
CLAVETERC = 'rebotes'
CLAVECUAT = 'triples'
CLAVEQUIN = 'valJornada'
CLAVESEX = 'broker'

from collections import defaultdict
from itertools import combinations, product
from math import log10
from os.path import join
from time import asctime, strftime

from configargparse import ArgumentParser
from joblib import Parallel, delayed

from SMACB.SMconstants import (CUPOS, POSICIONES, buildPosCupoIndex,
                               calculaValSuperManager)
from SMACB.SuperManager import ResultadosJornadas, SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.CombinacionesConCupos import GeneraCombinaciones, calculaClaveComb
from Utils.combinatorics import n_choose_m, prod
from Utils.Misc import FORMATOtimestamp


def listaPosiciones():
    return [None] * 9


def calcFileName(jornada, indice, cantidad, dirbase="/tmp"):
    nomfich = "J%02i-%02i-%02i.lst" % (jornada, indice, cantidad)
    return join(dirbase, nomfich)


def generaCombinacion(datos, n):
    if n == 0:
        return dict()

    numcombs = 0
    colvalores = defaultdict(list)

    for p in combinations(datos, n):
        total = [0] * (len(datos[0]) - 1)
        jugs = [x[0] for x in p]

        for x in p:
            for i in range(len(total)):
                total[i] += x[i + 1]

        numcombs += 1
        colvalores[total[0]].append(["-".join(jugs)] + total[1:])

    return colvalores


def buscaCombinacionesSumas(datos, combinacion, valoresobj):
    resultados = defaultdict(list)
    valoresdest = set(valoresobj.keys())

    def pruebaCombs(acum, i, datos, combinacion, solucion, valores):
        if i < 0:
            if acum in valores:
                resultados[acum].append((combinacion, solucion))
                # print("Solucion! [%s] %s -> %s" % (combinacion,acum, solucion))
            return

        if not combinacion[i]:
            pruebaCombs(acum, i - 1, datos, combinacion, solucion, valores)
            return

        if not len(datos[i][combinacion[i]]):
            pruebaCombs(acum, i - 1, datos, combinacion, solucion, valores)
            return

        for res in datos[i][combinacion[i]]:
            newSol = solucion.copy()
            newSol[i] = res
            pruebaCombs(acum + res, i - 1, datos, combinacion, newSol, valores)
        return

    solBase = [None] * len(combinacion)

    pruebaCombs(0, len(combinacion) - 1, datos, combinacion, solBase, valoresdest)
    print(asctime(), combinacion, " -> ", ["%s -> %d" % (x, len(resultados[x])) for x in sorted(resultados)],
          sum([len(resultados[x]) for x in resultados]))

    return resultados


def buscaCombinacionesSumasConVal(datos, combinacion, valoresobj):
    resultados = defaultdict(list)
    valoresdest = set(valoresobj.keys())

    def pruebaCombs(acum, i, datos, combinacion, solucion, valores):
        if i < 0:
            if acum in valores:
                for d in compruebaEquiposSingle(solucion, combinacion, datos, valoresobj[acum], acum):
                    resultados[acum].append(d)
                # print("Solucion! [%s] %s -> %s" % (combinacion,acum, solucion))
            return

        if not combinacion[i]:
            pruebaCombs(acum, i - 1, datos, combinacion, solucion, valores)
            return

        if not len(datos[i][combinacion[i]]):
            pruebaCombs(acum, i - 1, datos, combinacion, solucion, valores)
            return

        for res in datos[i][combinacion[i]]:
            newSol = solucion.copy()
            newSol[i] = res
            pruebaCombs(acum + res, i - 1, datos, combinacion, newSol, valores)
        return

    solBase = [None] * len(combinacion)

    pruebaCombs(0, len(combinacion) - 1, datos, combinacion, solBase, valoresdest)
    print(asctime(), combinacion, " -> ", ["%s -> %d" % (x, len(resultados[x])) for x in sorted(resultados)],
          sum([len(resultados[x]) for x in resultados]))

    return resultados


def combinacionesParallel(comb, datos, valores):
    agrporValores = [(len(datos[c][m]) if m else 1) for (c, m) in zip(range(len(comb)), comb)]
    totV = prod(agrporValores)
    # print("%18d -> %35s" % (tot, numcombs))
    print("%s: %s %18d (%.5f)" % (asctime(), comb, totV, log10(totV)))

    res = buscaCombinacionesSumas(datos, comb, valores)

    return res


def combinacionesParallelConV(comb, datos, valores):
    agrporValores = [(len(datos[c][m]) if m else 1) for (c, m) in zip(range(len(comb)), comb)]
    totV = prod(agrporValores)
    # print("%18d -> %35s" % (tot, numcombs))
    print("%s: %s %18d (%.5f)" % (asctime(), comb, totV, log10(totV)))

    res = buscaCombinacionesSumasConVal(datos, comb, valores)

    return res


def compruebaEquipos(datos):
    resultados = defaultdict(list)

    def comparaDatos(x, y):
        eq1 = [0 if xi == yi else 1 for (xi, yi) in zip(x[1:], y[1:])]
        return sum(eq1) == 0

    def mergeDatos(x, y):
        res = [a + d for (a, d) in zip(x, y)]
        res[0] = x[0] + ("-" if x[0] else "") + y[0]
        return res

    def pruebaCombs(acum, i, datos, valores, suma):
        if i < 0:
            for v in valores:
                if comparaDatos(acum, v):
                    print("Solucion: ", acum)
                    resultados[suma].append(acum)
                # print("Solucion! [%s] %s -> %s" % (combinacion,acum, solucion))
            return

        if datos[i] is None:
            pruebaCombs(acum, i - 1, datos, valores, suma)
            return

        if not len(datos[i]):
            pruebaCombs(acum, i - 1, datos, valores, suma)
            return

        for res in datos[i]:
            acumSum = mergeDatos(acum, res)
            pruebaCombs(acumSum, i - 1, datos, valores, suma)
        return

    for comb in datos:
        sumaObj = comb[0]
        valores = comb[2]
        datosAcomb = comb[1]
        acumOtros = [""] + [0] * (len(valores[0]) - 1)
        pruebaCombs(acumOtros, len(datosAcomb) - 1, datosAcomb, valores, sumaObj)

    return resultados


def compruebaEquiposSingle(solucion, combinacion, datos, valores, suma):
    # print(solucion, combinacion, valores, suma )
    resultados = list()

    def comparaDatos(x, y):
        eq1 = [0 if xi == yi else 1 for (xi, yi) in zip(x[1:], y[1:])]
        return sum(eq1) == 0

    def mergeDatos(x, y):
        res = [a + d for (a, d) in zip(x, y)]
        res[0] = x[0] + ("-" if x[0] else "") + y[0]
        return res

    def pruebaCombs(acum, i, datos, valores, suma):
        if i < 0:
            for v in valores:
                if comparaDatos(acum, v):
                    # print("Solucion: ", acum, v)
                    resultados.append((acum, v))
                # print("Solucion! [%s] %s -> %s" % (combinacion,acum, solucion))
            return

        if datos[i] is None:
            pruebaCombs(acum, i - 1, datos, valores, suma)
            return

        if not len(datos[i]):
            pruebaCombs(acum, i - 1, datos, valores, suma)
            return

        for res in datos[i]:
            acumSum = mergeDatos(acum, res)
            pruebaCombs(acumSum, i - 1, datos, valores, suma)
        return

    listaCupos = [datos[n][m][p] if m else None for (n, m, p) in zip(range(len(combinacion)),
                                                                     combinacion, solucion)]
    acumOtros = [""] + [0] * (len(valores[0]) - 1)
    pruebaCombs(acumOtros, len(listaCupos) - 1, listaCupos, valores, suma)

    return resultados


def validaEquiposParallel(comb, datos, valores):
    if not comb:
        return list()

    totV = 0
    combsAProcesar = list()
    for sumSM in comb:
        for comb1 in comb[sumSM]:
            combCupos = comb1[0]
            puntosComb = comb1[1]
            listaCupos = [datos[n][m][p] if m else None for (n, m, p) in zip(range(len(combCupos)),
                                                                             combCupos, puntosComb)]
            agrporValores = [(len(m) if m else 1) for m in listaCupos]
            combsAProcesar.append((sumSM, listaCupos, valores[sumSM]))

            totV += prod(agrporValores)

    print("%s: %18d (%.5f)" % (asctime(), totV, log10(totV)))

    res = compruebaEquipos(combsAProcesar)

    return res


# def precalculaCombsPosYCupo(posYcupos, combTeams):
#     nonePlayer = {'cod': None}
#     result = [dict()] * 9
#
#     posValues = defaultdict(set)
#
#     for comb in combTeams:
#         for idx in range(len(comb)):
#             posValues[idx].add(comb[idx])
#
#     for idx in posValues:
#         print(idx)
#
#         for n in posValues[idx]:
#             print(idx, n)
#
#             aux = defaultdict(list)
#
#             jugsToMatch = posYcupos['data'][idx]
#             # Añade tantos None (vacios) como jugs posibles
#             for i in range(n):
#                 jugsToMatch.append(nonePlayer)
#
#             for c in combinations(jugsToMatch, n):
#                 rt = agregaJugadores(c)
#                 aux[rt['valJornada']].append(rt)
#
#             result[idx][n] = aux
#             return result
#
#     return result
#

def agregaJugadores(listaJugs, datosJugs):
    tradKEys = {'broker': 'difPrecio', 'puntos': 'P', 'rebotes': 'REB-T', 'triples': 'T3-C', 'asistencias': 'A'}
    result = {'jugs': list(), 'valJornada': 0, 'broker': 0, 'puntos': 0, 'rebotes': 0, 'triples': 0, 'asistencias': 0,
              'Nones': 0}

    for j in listaJugs:
        if j is None:
            result['Nones'] += 1
            continue
        result['jugs'].append(j)
        for k in ['valJornada', 'broker', 'puntos', 'rebotes', 'triples', 'asistencias']:
            targKey = tradKEys.get(k, k)
            result[k] += datosJugs[j].get(targKey, 0)

    return result


def CalcCombinaciones(mercado, valores, jornada=0, resTemporada=None):
    resultado = defaultdict(list)
    posYcupos = mercado.getPlayersByPosAndCupo(jornada, resTemporada)

    combTeams = GeneraCombinaciones()

    print(combTeams)

    return

    maxNum = [0] * len(CUPOS) * len(POSICIONES)

    for i in range(len(maxNum)):
        uso = [x[i] for x in combTeams]
        usoStat = defaultdict(int)
        for x in uso:
            usoStat[x] += 1
        # print(i, usoStat)
        maxNum[i] = max(uso)

    preCalcListas = defaultdict(list)

    for i in range(len(maxNum)):
        uso = [x[i] for x in combTeams]
        maxNumI = max(uso)
        preCalcListas[i] = defaultdict(set)

        for n in range(maxNumI + 1):
            preCalcListas[i][n] = generaCombinacion(posYcupos['data'][i], n)

    if 1:
        datosRecort = [combTeams[x] for x in range(1)]
        resultado = Parallel(n_jobs=ncpu - 1)(delayed(combinacionesParallelConV)(comb,
                                                                                 preCalcListas,
                                                                                 valores) for comb in datosRecort)
    else:
        for comb in combTeams:
            res = combinacionesParallel(comb, preCalcListas, valores)

            for punt in res:
                for wincomb in res[punt]:
                    mergComb = zip(range(len(comb)), wincomb[0], wincomb[1])
                    valCombs = []
                    for c in mergComb:
                        if not c[1]:
                            continue
                        valCombs.append(preCalcListas[c[0]][c[1]][c[2]])
                    resultado[punt].append(valCombs)

    return resultado


def getPartidosJornada(jornada, temporada):
    result = []

    if jornada not in temporada.Calendario.Jornadas:
        return result

    return [temporada.Partidos[x] for x in temporada.Calendario.Jornadas[jornada]['partidos']]


def getPlayersByPosAndCupo(jornada, supermanager, temporada):
    result = []

    if jornada not in supermanager.mercadoJornada:
        return result

    mercadoFin = supermanager.mercado[supermanager.mercadoJornada[jornada]]

    partidos = getPartidosJornada(jornada, temporada)

    minTimestamp = min([x.timestamp for x in partidos])
    idMercadoIni = max([x for x in supermanager.mercado if supermanager.mercado[x].timestamp < minTimestamp])
    mercadoIni = supermanager.mercado[idMercadoIni]

    partidosOk = [x for x in partidos if x.timestamp < mercadoFin.timestamp]

    dictJugs = defaultdict(dict)

    for j in mercadoIni.PlayerData:
        dictJugs[j]['code'] = j
        dictJugs[j]['cupo'] = mercadoIni.PlayerData[j]['cupo']
        dictJugs[j]['pos'] = mercadoIni.PlayerData[j]['pos']
        dictJugs[j]['precioIni'] = mercadoIni.PlayerData[j]['precio']
        if j not in mercadoFin.PlayerData:
            raise KeyError("Clave '%s' (%s) inexistente en mercadoFin" % (j, mercadoIni.PlayerData[j]['nombre']))

        dictJugs[j]['precioFin'] = mercadoFin.PlayerData[j]['precio']
        dictJugs[j]['valJornada'] = mercadoFin.PlayerData[j]['valJornada']
        dictJugs[j]['difPrecio'] = dictJugs[j]['precioFin'] - dictJugs[j]['precioIni']

    for p in partidosOk:
        for j in p.Jugadores:
            if j in dictJugs:
                for c in ['P', 'A', 'V', 'T3-C', 'REB-T']:
                    dictJugs[j][c] = p.Jugadores[j]['estads'].get(c, 0)
                dictJugs[j]['valSM'] = calculaValSuperManager(p.Jugadores[j]['estads'].get('V', 0),
                                                              p.Jugadores[j]['haGanado'])

    indexPosCupo = buildPosCupoIndex()
    result = defaultdict(list)

    for j in dictJugs:
        pos = dictJugs[j]['pos']
        cupo = dictJugs[j]['cupo']
        i = indexPosCupo[pos][cupo]
        result[i].append(j)

    return indexPosCupo, result, dictJugs


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
    aux = defaultdict(list)
    contStats = defaultdict(lambda: defaultdict(int))

    valoresPRINC = resultadosSM.valoresSM()[CLAVEPRINC]
    valoresSEC = resultadosSM.valoresSM()[CLAVESEC]
    valoresTERC = resultadosSM.valoresSM()[CLAVETERC]
    valoresCUAT = resultadosSM.valoresSM()[CLAVECUAT]
    valoresQUIN = resultadosSM.valoresSM()[CLAVEQUIN]
    valoresSEX = resultadosSM.valoresSM()[CLAVESEX]

    teamsRES = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda : defaultdict(list))))))

    for t in resultadosSM.resultados:
        teamsRES[resultadosSM.resultados[t][CLAVEPRINC]][resultadosSM.resultados[t][CLAVESEC]][resultadosSM.resultados[t][CLAVETERC]][resultadosSM.resultados[t][CLAVECUAT]][resultadosSM.resultados[t][CLAVEQUIN]][resultadosSM.resultados[t][CLAVESEX]].append(t)

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

            terCombsToTest = [se[x] for x,se in zip(prSEC,secCombsToTest)]
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

                cuatCombsToTest = [se[x] for x,se in zip(prTERC,terCombsToTest)]
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

                    quinCombsToTest = [se[x] for x,se in zip(prCUAT,cuatCombsToTest)]
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

                        sexCombsToTest = [se[x] for x,se in zip(prQUIN,quinCombsToTest)]
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

                            finCombsToTest = [se[x] for x,se in zip(prSEX,sexCombsToTest)]
                            remainers += prod([len(x) for x in finCombsToTest])
                            sol = list(zip(POSICIONES, comb, prPRINC, prSEC, prTERC, prCUAT, prQUIN, prSEX, [len(x) for x in finCombsToTest]))
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
                                    if resultadosSM.comparaAgregado(t,agr):
                                        print("Si!", comb, jugList)
                                        result[t].append(jugList)


    # print(asctime(), comb, "OUT", prOrig, prSets, len(result), {x:len(result[x]) for x in result})
    print(asctime(), comb, "OUT", prOrig, prSets, prOrig / prSets, remainers, contStats, ) # {x:result[x] for x in result}
    return result


def GeneraCombinacionJugs(listaJugs, n):
    result = []

    for i in combinations(listaJugs, n):
        result.append(i)

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
    puntosSM = resJornada.valoresSM()

    # Recupera los datos de los jugadores que han participado en la jornada
    indexes, posYcupos, jugadores = getPlayersByPosAndCupo(args.jornada, sm, temporada)

    validCombs = GeneraCombinaciones()
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
                    colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]][agr[CLAVEQUIN]] = defaultdict(list)

                colSets[agr[CLAVEPRINC]][agr[CLAVESEC]][agr[CLAVETERC]][agr[CLAVECUAT]][agr[CLAVEQUIN]][agr[CLAVESEX]].append(claveJugs)

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

    result = Parallel(n_jobs=2)(delayed(validateCombs)(c, cuentaGrupos, resJornada, jugadores) for c in groupedCombs)

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
    print(puntosSM)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from collections import defaultdict
from itertools import combinations
from math import log10
from multiprocessing import cpu_count
from os.path import join
from time import asctime, strftime

from configargparse import ArgumentParser

from joblib import Parallel, delayed
from SMACB.SMconstants import CUPOS, POSICIONES
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.CombinacionesConCupos import GeneraCombinaciones
from Utils.combinatorics import prod
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


def getPlayersByPosAndCupo(listaJugs):
    result = {'data': defaultdict(list),
              'cont': [0] * len(POSICIONES) * len(CUPOS)}
    indexResult = {}

    aux = 0
    for pos in POSICIONES:
        indexResult[pos] = {}
        for cupo in CUPOS:
            indexResult[pos][cupo] = aux
            aux += 1
    result['indexes'] = indexResult

    for cod in listaJugs:
        datos = listaJugs[cod]
        datos['cod'] = cod
        i = indexResult[datos['pos']][datos['cupo']]

        (result['data'][i]).append(datos)
        result['cont'][i] += 1

    return result


def precalculaCombsPosYCupo(posYcupos, combTeams):
    nonePlayer = {'cod': None}
    result = [dict()] * 9

    posValues = defaultdict(set)

    for comb in combTeams:
        for idx in range(len(comb)):
            posValues[idx].add(comb[idx])

    for idx in posValues:
        print(idx)

        for n in posValues[idx]:
            print(idx, n)

            aux = defaultdict(list)

            jugsToMatch = posYcupos['data'][idx]
            # Añade tantos None (vacios) como jugs posibles
            for i in range(n):
                jugsToMatch.append(nonePlayer)

            for c in combinations(jugsToMatch, n):
                rt = agregaJugadores(c)
                aux[rt['valJornada']].append(rt)

            result[idx][n] = aux
            return result

    return result


def agregaJugadores(listaJugs):
    result = {'jugs': list(), 'valJornada': 0, 'broker': 0, 'puntos': 0, 'rebotes': 0, 'triples': 0, 'asistencias': 0,
              'Nones': 0}

    for j in listaJugs:
        if j['cod'] is None:
            result['Nones'] += 1
            continue
        result['jugs'].append(j['cod'])
        for k in ['valJornada', 'broker', 'puntos', 'rebotes', 'triples', 'asistencias']:
            result[k] += j.get(k, 0)

    return result


def CalcCombinaciones(mercado, valores, jornada=0, resTemporada=None):
    resultado = defaultdict(list)
    posYcupos = mercado.getPlayersByPosAndCupo(jornada, resTemporada)

    combTeams = GeneraCombinaciones()

    # print(combTeams)

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


if __name__ == '__main__':

    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)
    parser.add('-j', dest='jornada', type=int, required=False)

    args = parser.parse_args()
    jornadaList = []
    sm = SuperManagerACB()
    if 'infile' in args and args.infile:
        sm.loadData(args.infile)
        print("Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    if 'jornada' in args and args.jornada:
        jornadaList.append(args.jornada)
    else:
        jornadaList = list(sm.mercado.keys())

    temporada = None
    resultadoTemporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)
        resultadoTemporada = temporada.extraeDatosJugadores()
        print("Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))

    badTeams = [x for x in (sm.jornadas[1].data.keys()) if 'Pablosky' in x]
    ncpu = cpu_count()

    for j in jornadaList:
        # resJornada = ResultadosJornadas(j, sm, excludelist=badTeams)
        resJornada = sm.diffJornadas(j, excludeList=badTeams)
        jugSMjornada = sm.diffMercJugadores(j)
        jugTMjornada = temporada.extraeDatosJornadaSM(j)
        listaJugs = dict()

        for j in jugSMjornada:
            listaJugs[j] = jugSMjornada[j]
            if j in jugTMjornada:
                listaJugs[j].update(jugTMjornada[j])

        posYcupos = getPlayersByPosAndCupo(listaJugs)
        combTeams = GeneraCombinaciones()

        d1 = precalculaCombsPosYCupo(posYcupos, combTeams)
        print(d1)

        continue

        puntosSM = resJornada.valoresSM()

        merc = sm.mercado[sm.mercadoJornada[j]]

        combs = CalcCombinaciones(merc, puntosSM, j, resultadoTemporada)
        print(combs)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from collections import defaultdict
from itertools import combinations
from math import log10

from SMACB.MercadoPage import MercadoPageContent
from SMACB.SMconstants import CUPOS, POSICIONES
from Utils.CombinacionesConCupos import GeneraCombinaciones
from Utils.combinatorics import n_choose_m, prod
from Utils.Misc import ReadFile

mf = ReadFile("/home/calba/Dropbox/SuperManager/SuperManager-201809280846.html")
co = MercadoPageContent(mf)
posYcupos = co.getPlayersByPosAndCupo()

print(posYcupos)
combTeams = GeneraCombinaciones()

maxNum = [0] * len(CUPOS) * len(POSICIONES)

for i in range(len(maxNum)):
    uso = [x[i] for x in combTeams]
    usoStat = defaultdict(int)
    for x in uso:
        usoStat[x] += 1
    print(i, usoStat)
    maxNum[i] = max(uso)

preCalcListas = [[]] * len(CUPOS) * len(POSICIONES)

for i in range(len(maxNum)):
    uso = [x[i] for x in combTeams]
    maxNumI = max(uso)
    preCalcListas[i] = [[]] * (maxNumI + 1)
    for n in range(maxNumI + 1):
        print(i, n, posYcupos['cont'][i], n_choose_m(posYcupos['cont'][i], n))
        continue
        if n_choose_m(posYcupos['cont'][i], n) > 1000000:
            preCalcListas[i][n]
            continue
        listaAux = []
        for comb in combinations(posYcupos['data'][i], n):
            combJug = []
            valTotal = 0
            for jug in comb:
                combJug.append(jug[0])
                valTotal += jug[1]
            listaAux.append((combJug.copy(), valTotal))
        preCalcListas[i][n] = listaAux.copy()

print(preCalcListas)

cont = 0
for comb in combTeams:
    numcombs = [n_choose_m(n, m) for (n, m) in zip(posYcupos['cont'], comb)]
    tot = prod(numcombs)
    print("%18d -> %35s" % (tot, numcombs))
    cont += tot
    comb0 = combinations(posYcupos['data'][0], comb[0])
    comb1 = combinations(posYcupos['data'][1], comb[1])
    comb2 = combinations(posYcupos['data'][2], comb[2])
    comb3 = combinations(posYcupos['data'][3], comb[3])
    comb4 = combinations(posYcupos['data'][4], comb[4])
    comb5 = combinations(posYcupos['data'][5], comb[5])
    comb6 = combinations(posYcupos['data'][6], comb[6])
    comb7 = combinations(posYcupos['data'][7], comb[7])
    comb8 = combinations(posYcupos['data'][8], comb[8])
    # for comb in product(comb0,comb1,comb2,comb3,comb4,comb5

print("%18d " % (cont), log10(cont))

# print(posYcupos)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import bz2
import csv
from collections import defaultdict
from itertools import chain, product
from time import asctime, strftime, time

import joblib
from configargparse import ArgumentParser
from dask.distributed import Client

from SMACB.Guesser import (GeneraCombinacionJugs, agregaJugadores,
                           buildPosCupoIndex, combPos2Key, dumpVar,
                           getPlayersByPosAndCupoJornada, loadVar,
                           varname2fichname)
from SMACB.SMconstants import CUPOS, POSICIONES, SEQCLAVES
from SMACB.SuperManager import ResultadosJornadas, SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.CombinacionesConCupos import GeneraCombinaciones, calculaClaveComb
from Utils.combinatorics import n_choose_m, prod
from Utils.Misc import FORMATOtimestamp, deepDict, deepDictSet

NJOBS = 2
LOCATIONCACHE = '/var/tmp/joblibCache'
LOCATIONCACHE = '/home/calba/devel/SuperManager/guesser'

CLAVESCSV = ['solkey', 'grupo', 'jugs', 'valJornada', 'broker', 'puntos', 'rebotes', 'triples', 'asistencias', 'Nones']

indexes = buildPosCupoIndex()


# Planes con solucion usuario    Pabmm, J5

def solucion2clave(clave, sol, charsep="#"):
    formatos = {'asistencias': "%03d", 'triples': "%03d", 'rebotes': "%03d", 'puntos': "%03d", 'valJornada': "%05.2f",
                'broker': "%010d"}
    formatoTotal = charsep.join([formatos[k] for k in SEQCLAVES])
    valores = [sol[k] for k in SEQCLAVES]

    return clave + "#" + (formatoTotal % tuple(valores))


def procesaArgumentos():
    parser = ArgumentParser()

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)
    parser.add('-j', dest='jornada', type=int, required=True)

    parser.add('-s', '--include-socio', dest='socioIn', type=str, action="append")
    parser.add('-e', '--exclude-socio', dest='socioOut', type=str, action="append")
    parser.add('-l', '--lista-socios', dest='listaSocios', action="store_true", default=False)

    parser.add('-b', '--backend', dest='backend', choices=['local', 'yarn', 'remote'], default='local')
    parser.add('-x', '--scheduler', dest='scheduler', type=str, default='127.0.0.1')
    parser.add("-o", "--output-dir", dest="outputdir", type=str, default=LOCATIONCACHE)
    parser.add('-p', '--package', dest='package', type=str, action="append")

    parser.add('--nproc', dest='nproc', type=int, default=NJOBS)

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    args = parser.parse_args()

    return args


def validateCombs(comb, grupos2check, val2match, equipo):
    result = []

    contExcl = {'in': 0, 'out': 0}

    claves = SEQCLAVES.copy()

    combVals = [grupos2check[p]['valSets'] for p in POSICIONES]
    combInt = [grupos2check[p]['comb'] for p in POSICIONES]

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
                solAcum = {k: sum(s) for k, s in zip(SEQCLAVES, nuevaSol)}
                for k in SEQCLAVES:
                    assert (solAcum[k] == val2match[k])

                valsSolD = [dict(zip(SEQCLAVES, s)) for s in list(zip(*nuevaSol))]
                solClaves = [solucion2clave(c, s) for c, s in zip(comb, valsSolD)]

                regSol = (equipo, solClaves, prod([x for x in nuevosCombVals]))
                result.append(regSol)
                # TODO: logging
                print(asctime(), equipo, combInt, "Sol", regSol)
                continue
            else:
                deeperSol = curSol + [prodKey]
                deeper = ValidaCombinacion(nuevosCombVals, claves[1:], val2match, deeperSol)
                if deeper is None:
                    continue
        return None

    solBusq = ",".join(["%s:%s" % (k, str(val2match[k])) for k in SEQCLAVES])
    numCombs = prod([grupos2check[p]['numCombs'] for p in POSICIONES])
    print(asctime(), equipo, combInt, "IN  ", numCombs, solBusq)
    timeIn = time()
    ValidaCombinacion(combVals, claves, val2match, [])
    timeOut = time()
    durac = timeOut - timeIn

    numEqs = sum([eq[-1] for eq in result])
    ops = contExcl['in'] + contExcl['out']
    descIn = contExcl['in']
    descOut = contExcl['out']

    print(asctime(), equipo, combInt, "OUT %3d %3d %10.6f %.6f%% %d -> %8d (%d,%d)" % (
        len(result), numEqs, durac, (100.0 * float(ops) / float(numCombs)), numCombs, ops, descIn, descOut), contExcl)

    return result


def cuentaCombinaciones(combList):
    result = []
    resultKeys = []
    for c in combList:
        newComb = []
        newCombKey = []

        for p in POSICIONES:
            indexGrupo = [indexes[p][x] for x in CUPOS]
            grupoComb = [c[i] for i in indexGrupo]
            newComb.append(grupoComb)
            newCombKey.append(combPos2Key(grupoComb, p))
            # claveComb = p + "-" + calculaClaveComb(grupoComb)
        result.append(newComb)
        resultKeys.append(newCombKey)

    return result, resultKeys


if __name__ == '__main__':
    print(asctime(), "Comenzando ejecución")

    args = procesaArgumentos()
    jornada = args.jornada
    destdir = args.outputdir

    # TODO: Control de calidad con los parámetros
    if args.backend == 'local':
        pass

    elif args.backend == 'remote':
        error = 0
        if 'scheduler' not in args:
            print(asctime(), "Backend: %s. Falta scheduler '-x' o '--scheduler'.")
            error += 1
        if 'package' not in args:
            print(asctime(), "Backend: %s. Falta package '-p' o '--package'.")
            error += 1
        if error:
            print(asctime(), "Backend: %s. Hubo %d errores. Saliendo." % (args.backend, error))
            exit(1)

        client = Client('tcp://%s:8786' % args.scheduler)
        for egg in args.package:
            client.upload_file(egg)
        configParallel = {'verbose': 100, 'backend': "dask", 'scheduler_host': (args.scheduler, 8786)}

    elif args.backend == 'yarn':
        error = 0
        if 'package' not in args:
            print(asctime(), "Backend: %s. Falta package '-p' o '--package'.")
            error += 1
        if error:
            print(asctime(), "Backend: %s. Hubo %d errores. Saliendo." % (args.backend, error))
            exit(1)

    else:
        pass

    # Carga datos
    sm = SuperManagerACB()
    if 'infile' in args and args.infile:
        sm.loadData(args.infile)
        print(asctime(), "Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    temporada = None
    resultadoTemporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)
        resultadoTemporada = temporada.extraeDatosJugadores()
        print(asctime(), "Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))

    badTeams = args.socioOut if args.socioOut is not None else []

    # Recupera resultados de la jornada
    resJornada = ResultadosJornadas(jornada, sm)
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

    sociosReales = [s for s in goodTeams if s in resJornada.socio2equipo and s not in badTeams]

    if not sociosReales:
        print(asctime(), "No hay socios que procesar. Saliendo")
        exit(1)

    jugadores = None

    validCombs = GeneraCombinaciones()
    # validCombs = pabloPlans

    groupedCombs, groupedCombsKeys = cuentaCombinaciones(validCombs)

    print(asctime(), "Cargando grupos de jornada %d" % jornada)
    cuentaGrupos = loadVar(varname2fichname(jornada=jornada, varname="cuentaGrupos", basedir=destdir))

    if cuentaGrupos is None:

        posYcupos, jugadores, lenPosCupos = getPlayersByPosAndCupoJornada(jornada, sm, temporada)

        dumpVar(varname2fichname(jornada, "jugadores", basedir=destdir), jugadores)

        # groupedCombs = []
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

        indexGroups = {p: [indexes[p][c] for c in CUPOS] for p in POSICIONES}

        # Distribuciones de jugadores válidas por posición y cupo
        for c in groupedCombs:
            posGrupoPars = [(p, g) for p, g in zip(POSICIONES, c)]
            for p, grupoComb in posGrupoPars:
                claveComb = p + "-" + calculaClaveComb(grupoComb)
                if claveComb not in cuentaGrupos[p]:
                    numCombs = prod([numCombsPosYCupos[x[0]][x[1]] for x in zip(indexGroups[p], grupoComb)])
                    cuentaGrupos[p][claveComb] = {'cont': 0, 'comb': grupoComb, 'numCombs': numCombs,
                                                  'indexes': indexGroups[p],
                                                  'pos': p, 'key': claveComb}
                cuentaGrupos[p][claveComb]['cont'] += 1

        for p in cuentaGrupos:
            print(asctime(), p, len(cuentaGrupos[p]))
            for c in cuentaGrupos[p]:
                print(asctime(), "   ", c, cuentaGrupos[p][c])
            print(asctime(), sum([cuentaGrupos[p][x]['numCombs'] for x in cuentaGrupos[p]]))

        with bz2.open(filename=varname2fichname(jornada, "grupos", basedir=destdir, ext="csv.bz2"),
                      mode='wt') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CLAVESCSV, delimiter="|")
            for p in POSICIONES:
                for comb in cuentaGrupos[p]:
                    combList = []

                    combGroup = cuentaGrupos[p][comb]['comb']
                    index = cuentaGrupos[p][comb]['indexes']
                    timeIn = time()
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
                        claveJugs = "-".join(aux)
                        indexComb = [agr[k] for k in SEQCLAVES]
                        agr['solkey'] = solucion2clave(comb, agr)
                        agr['grupo'] = comb
                        agr['jugs'] = claveJugs
                        writer.writerow(agr)

                        deepDictSet(colSets, indexComb, deepDict(colSets, indexComb, int) + 1)

                    timeOut = time()
                    duracion = timeOut - timeIn
                    print(asctime(), comb, "%10.6f" % duracion, cuentaGrupos[p][comb])

                    cuentaGrupos[p][comb]['valSets'] = colSets

        resDump = dumpVar(varname2fichname(jornada=jornada, varname="cuentaGrupos", basedir=destdir),
                          cuentaGrupos)

    print(asctime(), "Cargados %d grupos de combinaciones." % len(cuentaGrupos))

    resultado = dict()

    planesAcorrer = []
    sociosReales.sort()
    for plan, socio in product(groupedCombsKeys, sociosReales):
        planTotal = {'comb': plan,
                     'grupos2check': {pos: cuentaGrupos[pos][grupo] for pos, grupo in zip(POSICIONES, plan)},
                     'val2match': resJornada.resultados[socio],
                     'equipo': socio}
        planesAcorrer.append(planTotal)

    print(asctime(), "Planes para ejecutar: %d" % len(planesAcorrer))

    with joblib.parallel_backend('dask'):
        result = joblib.Parallel(configParallel)(joblib.delayed(validateCombs)(**plan) for plan in planesAcorrer)

    # result = Parallel(**configParallel)(delayed(validateCombs)(**plan) for plan in planesAcorrer)
    resultadoPlano = list(chain.from_iterable(result))
    dumpVar(varname2fichname(jornada, "resultado-planes" % "-".join(sociosReales), basedir=destdir), resultadoPlano)

    print(asctime(), resultadoPlano)
    # print(acumOrig, acumSets)

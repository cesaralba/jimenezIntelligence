#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from statistics import mean, median, stdev
from time import gmtime, mktime, strftime, time

from CAPcore.Misc import FORMATOtimestamp, SubSet
from SMACB.SuperManager import SuperManagerACB
from configargparse import ArgumentParser
from pandas import DataFrame, ExcelWriter

from SMACB.Constants import MINPRECIO, POSICIONES, PRECIOpunto
from SMACB.ManageSMDataframes import (calculaDFcategACB, calculaDFconVars, calculaDFprecedentes, CATMERCADOFINAL,
                                      COLSPREC)
from SMACB.PartidoACB import PartidoACB
from SMACB.TemporadaACB import calculaVars, calculaZ, TemporadaACB


def jugadoresMezclaStatus(datos):
    resultado = defaultdict(set)

    for jug in datos:
        datosJug = datos[jug]
        if 'I-activo' not in datosJug:
            (resultado[None]).add(jug)
            continue

        statusJug = datosJug['I-activo']
        (resultado[statusJug]).add(jug)

    return resultado


def CuentaClavesPartido(x):
    if type(x) is not dict:
        raise ValueError("CuentaClaves: necesita un diccionario")

    resultado = defaultdict(int)

    for clave in x:
        valor = x[clave]

        if type(valor) is not PartidoACB:
            print("CuentaClaves: objeto de clave '%s' no es un PartidoACB, %s" % (clave, type(valor)))
            continue

        for subclave in valor.__dict__.keys():
            resultado[subclave] += 1

    return resultado


def mezclaJugadores(jugTemporada, jugSuperManager):
    resultado = defaultdict(dict)

    for claveSM in jugSuperManager:
        for jug in jugSuperManager[claveSM]:
            resultado[jug][claveSM] = jugSuperManager[claveSM][jug]

    for claveTM in jugTemporada:
        for jug in jugTemporada[claveTM]:
            resultado[jug][claveTM] = jugTemporada[claveTM][jug]

    return resultado


def preparaDatosComunes(datosMezclados):
    resultado = dict()
    datosCabecera = dict()

    titularCabecera = ['Pos', 'Cupo', 'Lesion', 'Nombre', 'Equipo', 'Promedio Val', 'Precio', 'Proximo Rival',
                       'Precio punto']

    jugadoresActivos = jugadoresMezclaStatus(datosMezclados)[True]
    # jugadoresInactivos = jugPorStatus[False]
    jugDataActivos = {x: datosMezclados[x] for x in jugadoresActivos}

    for jug in jugDataActivos:
        cabecJug = list()
        datosJug = jugDataActivos[jug]

        for campo in ['I-pos', 'I-cupo', 'I-lesion', 'I-nombre', 'I-equipo', 'I-promVal', 'I-precio']:
            if campo in datosJug:
                if campo == 'I-pos':
                    cabecJug.append(POSICIONES[datosJug[campo]])
                    continue
                elif campo == 'I-lesion':
                    salud = "Lesionado" if datosJug[campo] else ""
                    cabecJug.append(salud)
                    continue

                cabecJug.append(datosJug[campo])
            else:
                print("Falla clave:", campo, datosJug)
                exit(1)

        proxPartido = ("@" if datosJug['I-proxFuera'] else "") + datosJug['I-rival']
        cabecJug.append(proxPartido)
        costePunto = (datosJug['I-precio'] / datosJug['I-promVal']) if (datosJug['I-promVal']) > 0 else "-"
        cabecJug.append(costePunto)
        datosCabecera[jug] = cabecJug

    claves = list(map(lambda x: x[0],
                      sorted(list(map(lambda x: (x, jugDataActivos[x]['I-precio']), jugDataActivos)), reverse=True,
                             key=lambda x: x[1])))

    resultado['claves'] = claves
    resultado['cabeceraLinea'] = datosCabecera
    resultado['titularCabecera'] = titularCabecera

    return resultado


def preparaExcel(supermanager, temporada, nomFichero="/tmp/SM.xlsx"):
    dfSuperManager = supermanager.superManager2dataframe(
        nombresJugadores=temporada.tradJugadores['id2nombres'])  # Needed to get player position from all players
    dfTemporada = temporada.extraeDataframeJugadores().merge(dfSuperManager[['codigo', 'pos']], how='left')
    # All data fall playrs
    dfUltMerc = supermanager.mercado[supermanager.ultimoMercado].mercado2dataFrame()
    dfUltMerc['activo'] = True
    dfUltMerc['Alta'] = 'S'

    dfVZ = calculaZ(dfTemporada, 'V', useStd=True)

    varsVZ = calculaVars(dfTemporada, 'V')
    varsVsmZ = calculaVars(dfTemporada, 'Vsm')
    varsVD = calculaVars(dfTemporada, 'V', useStd=False)
    varsVsmD = calculaVars(dfTemporada, 'Vsm', useStd=False)

    dfPredsV = calculaDFconVars(dfTemp=dfTemporada, dfMerc=dfUltMerc, clave="V", filtroFechas=None)
    dfPredsVsm = calculaDFconVars(dfTemp=dfTemporada, dfMerc=dfUltMerc, clave="Vsm", filtroFechas=None)

    # numJornadas = temporada.maxJornada()
    # nombreJornadas = {False: temporada.Calendario.nombresJornada()[:numJornadas],
    #                   True: ['J 0'] + temporada.Calendario.nombresJornada()[:numJornadas]}

    def preparaFormatos(workbook):
        resultado = dict()

        for r in 'VD':
            for v in 'LF':
                newKey = r + v
                resultado[newKey] = workbook.add_format({'bg_color': 'green' if v == 'L' else 'blue'})
                resultado[newKey + 'd'] = workbook.add_format({'bg_color': 'green' if v == 'L' else 'blue'})
                resultado[newKey + 'n'] = workbook.add_format({'bg_color': 'green' if v == 'L' else 'blue'})
                resultado[newKey + 'dn'] = workbook.add_format({'bg_color': 'green' if v == 'L' else 'blue'})
                resultado[newKey + 'n'].set_italic()
                resultado[newKey + 'dn'].set_italic()

                if r == 'V':
                    resultado[newKey].set_bold()
                    resultado[newKey + 'd'].set_bold()
                    resultado[newKey + 'n'].set_bold()
                    resultado[newKey + 'dn'].set_bold()

        resultado['datosComunes'] = workbook.add_format({'num_format': '0.00;[Red]-0.00'})
        resultado['cabecera'] = workbook.add_format({'bold': True, 'align': 'center'})
        resultado['nulo'] = workbook.add_format()

        resultado['smBaja'] = workbook.add_format({'bg_color': 'grey'})

        return resultado

    def preparaHojaMercado(excelwriter, supermanager, temporada, listaformatos):
        dfSuperManager = supermanager.superManager2dataframe(
            nombresJugadores=temporada.tradJugadores['id2nombres'], )  # Needed to get player position from all players
        dfTemporada = temporada.extraeDataframeJugadores().merge(dfSuperManager[['codigo', 'pos']], how='left')
        # All data fall playrs
        dfUltMerc = supermanager.mercado[supermanager.ultimoMercado].mercado2dataFrame()
        auxPrecioObj = DataFrame({'obj': (dfUltMerc['promVal'] * PRECIOpunto), 'min': MINPRECIO}).max(axis=1)
        dfUltMerc['precObj'] = auxPrecioObj
        dfUltMerc['distAObj'] = dfUltMerc['precio'] - dfUltMerc['precObj']

        dfUltMerc['Alta'] = 'S'

        COLSDIFPRECIO = ['precObj', 'distAObj']

        dfPrecV = calculaDFprecedentes(dfTemporada, dfUltMerc, 'V')
        dfPrecVsm = calculaDFprecedentes(dfTemporada, dfUltMerc, 'Vsm')
        if dfPrecV.empty:
            antecColumns = CATMERCADOFINAL + COLSDIFPRECIO
            df2show = dfUltMerc[antecColumns].set_index('codigo')
        else:
            antecColumns = CATMERCADOFINAL + COLSDIFPRECIO + COLSPREC
            df2show = dfUltMerc.merge(dfPrecV, how='left').merge(dfPrecVsm, how='left')[antecColumns].set_index(
                'codigo')

        creaHoja(writer, 'Mercado', df2show, formatos, colsToFreeze=len(CATMERCADOFINAL) - 1)

    def calculaFormato(victoria, local, hajugado, vdecimal):
        if victoria is None:
            return "nulo"
        resultado = ""
        resultado += "V" if victoria else "D"
        resultado += "L" if local else "F"
        if vdecimal:
            resultado += "d"
        if hajugado is not None and hajugado:
            pass
        else:
            resultado += "n"

        return resultado

    def creaHoja(excelwriter, nombre, dataframe, formatos, rowsToFreeze=1, colsToFreeze=0, useIndex=False):

        dataframe.to_excel(excelwriter, sheet_name=nombre, freeze_panes=(rowsToFreeze, colsToFreeze), index=useIndex)

        sht = excelwriter.book.sheetnames[nombre]
        sht.autofilter(sht.dim_rowmin, sht.dim_colmin, sht.dim_rowmax, sht.dim_colmax)
        for r in range(sht.dim_rowmin + 1, sht.dim_rowmax + 1):
            sht.set_row(r, cell_format=formatos['datosComunes'])

    def addMetadata(excelwriter, sm, tm):

        metadata = ["Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp),
                    "Cargada información de temporada de %s" % strftime(FORMATOtimestamp, tm.timestamp),
                    "Ejecutado en %s" % strftime(FORMATOtimestamp, gmtime())]

        ws = excelwriter.book.add_worksheet("Metadata")
        fila = 0
        columna = 0
        for l in metadata:
            ws.write(fila, columna, l)
            fila += 1

    with ExcelWriter(nomFichero) as writer:
        formatos = preparaFormatos(writer.book)

        preparaHojaMercado(writer, sm, temporada, formatos)

        creaHoja(writer, 'V', calculaDFcategACB(dfTemporada, dfSuperManager, 'V'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'Vsm', calculaDFcategACB(dfTemporada, dfSuperManager, 'Vsm'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)

        creaHoja(writer, 'Z-V', calculaDFcategACB(dfVZ, dfSuperManager, 'Z-V'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'P', calculaDFcategACB(dfTemporada, dfSuperManager, 'P'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'A', calculaDFcategACB(dfTemporada, dfSuperManager, 'A'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'Rebotes', calculaDFcategACB(dfTemporada, dfSuperManager, 'REB-T'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'Triples', calculaDFcategACB(dfTemporada, dfSuperManager, 'T3-C'), formatos,
                 colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'PredicsV-Z', dfPredsV, formatos, colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'PredicsVsm-Z', dfPredsVsm, formatos, colsToFreeze=len(CATMERCADOFINAL) + 3)
        creaHoja(writer, 'TEMPORADA', dfTemporada, formatos, colsToFreeze=len(CATMERCADOFINAL) + 3)

        for comb in varsVZ:
            nombreHoja = "V-Z-" + comb
            indexCols = []
            if 'R' in comb:
                indexCols.append('CODrival')
            if 'P' in comb:
                indexCols.append('pos')
            if 'L' in comb:
                indexCols.append('esLocal')

            creaHoja(writer, nombreHoja, varsVZ[comb].set_index(indexCols), formatos, colsToFreeze=len(indexCols),
                     useIndex=True)

        for comb in varsVsmZ:
            nombreHoja = "Vsm-Z-" + comb
            indexCols = []
            if 'R' in comb:
                indexCols.append('CODrival')
            if 'P' in comb:
                indexCols.append('pos')
            if 'L' in comb:
                indexCols.append('esLocal')

            creaHoja(writer, nombreHoja, varsVsmZ[comb].set_index(indexCols), formatos, colsToFreeze=len(indexCols),
                     useIndex=True)

        for comb in varsVD:
            nombreHoja = "V-D-" + comb
            indexCols = []
            if 'R' in comb:
                indexCols.append('CODrival')
            if 'P' in comb:
                indexCols.append('pos')
            if 'L' in comb:
                indexCols.append('esLocal')

            creaHoja(writer, nombreHoja, varsVD[comb].set_index(indexCols), formatos, colsToFreeze=len(indexCols),
                     useIndex=True)

        for comb in varsVsmD:
            nombreHoja = "Vsm-D-" + comb
            indexCols = []
            if 'R' in comb:
                indexCols.append('CODrival')
            if 'P' in comb:
                indexCols.append('pos')
            if 'L' in comb:
                indexCols.append('esLocal')

            creaHoja(writer, nombreHoja, varsVsmD[comb].set_index(indexCols), formatos, colsToFreeze=len(indexCols),
                     useIndex=True)

        addMetadata(writer, sm, temporada)


def infoJugador(datosJugador, numdias=0):
    resultados = dict()
    Parts = dict()

    def auxDict():
        return defaultdict(int)

    Rjug = defaultdict(auxDict)
    Rvict = defaultdict(auxDict)

    haJugado = datosJugador['haJugado']
    esLocal = datosJugador['esLocal']
    victoria = datosJugador['haGanado']

    if numdias:
        fecha = [x for x in datosJugador['FechaHora']]
        partIDX = [i for i in range(len(haJugado)) if
                   haJugado[i] is not None and mktime(fecha[i]) > time() - (numdias * 24 * 3600)]
    else:
        partIDX = [i for i in range(len(haJugado)) if haJugado[i] is not None]

    Parts['total'] = [i for i in partIDX if esLocal[i] is not None]
    Parts['local'] = [i for i in Parts['total'] if esLocal[i]]
    Parts['fuera'] = [i for i in Parts['total'] if not esLocal[i]]

    for k in Parts:
        for i in Parts[k]:
            Rjug[k][haJugado[i]] += 1
            Rvict[k][victoria[i]] += 1

    for clave in ['V', 'P', 'A', 'T3-C', 'REB-T', 'Segs']:
        if clave not in datosJugador:
            continue
        resultados[clave] = defaultdict(dict)
        for k in Parts:
            auxVals = SubSet(datosJugador[clave], Parts[k])
            lv = len(auxVals)

            resultados[clave][k]['min'] = min(auxVals) if lv else "-"
            resultados[clave][k]['max'] = max(auxVals) if lv else "-"
            resultados[clave][k]['median'] = median(auxVals) if lv else "-"
            resultados[clave][k]['mean'] = mean(auxVals) if lv else "-"
            resultados[clave][k]['stdev'] = stdev(auxVals) if lv > 1 else "-"

    resultados['jug'] = Rjug
    resultados['vict'] = Rvict

    return resultados


if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)

    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)
    parser.add('-f', dest='filter', type=int, env_var='SM_DAYS', required=False, default=0)

    args = parser.parse_args()

    sm = SuperManagerACB()

    sm.loadData(args.infile)
    print("Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    temporada = TemporadaACB()
    temporada.cargaTemporada(args.temporada)
    print("Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))

    if 'outfile' in args and args.outfile:
        preparaExcel(sm, temporada, args.outfile)

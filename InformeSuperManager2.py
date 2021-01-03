#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from statistics import mean, median, stdev

from configargparse import ArgumentParser
from time import gmtime, mktime, strftime, time
from xlsxwriter import Workbook

from SMACB.Constants import POSICIONES
from SMACB.PartidoACB import PartidoACB
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import CuentaClaves, FORMATOtimestamp, SubSet


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

    titularCabecera = ['Pos', 'Cupo', 'Lesion', 'Nombre', 'Equipo', 'Promedio Val', 'Precio',
                       'Proximo Rival', 'Precio punto']

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

    claves = list(map(lambda x: x[0], sorted(list(map(lambda x: (x, jugDataActivos[x]['I-precio']), jugDataActivos)),
                                             reverse=True,
                                             key=lambda x: x[1])))

    resultado['claves'] = claves
    resultado['cabeceraLinea'] = datosCabecera
    resultado['titularCabecera'] = titularCabecera

    return resultado


def preparaExcel(supermanager, temporada, nomFichero="/tmp/SM.xlsx", ):
    jugSM = supermanager.extraeDatosJugadores()
    jugTM = temporada.extraeDatosJugadores()
    jugData = mezclaJugadores(jugTM, jugSM)
    numJornadas = temporada.maxJornada()
    nombreJornadas = {False: temporada.Calendario.nombresJornada()[:numJornadas],
                      True: ['J 0'] + temporada.Calendario.nombresJornada()[:numJornadas]}

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

    def creaHoja(workbook, nombre, clave, datosJugadores, datosComunes, formatos,
                 nombreJornadas, valorDecimal=False, claveSM=True):
        clavesExistentes = CuentaClaves(datosJugadores)

        if clave not in clavesExistentes:
            print("Clave '%s' no existente.\nClaves disponibles: %s" % (clave,
                                                                        ", ".join(map(
                                                                                lambda x: "'" + x + "'",
                                                                                sorted(clavesExistentes.keys())))))
            return

        seqDatos = list(range(numJornadas + (1 if claveSM else 0)))
        cabJornadas = nombreJornadas[claveSM]
        ot = -1 if claveSM else 0

        # print(ot, seqDatos, cabJornadas)

        ws = workbook.add_worksheet(nombre)

        fila, columna = 0, 0

        ws.write_row(fila, columna, datosComunes['titularCabecera'], formatos['cabecera'])
        columna += len(datosComunes['titularCabecera'])
        ws.write_row(fila, columna, cabJornadas, formatos['cabecera'])
        fila += 1
        columna = 0

        for jug in datosComunes['claves']:
            ws.write_row(fila, columna, datosComunes['cabeceraLinea'][jug], formatos['datosComunes'])
            columna += len(datosComunes['titularCabecera'])
            datosJugador = datosJugadores[jug]

            infoJugador(datosJugador, numdias=0)
            infoJugador(datosJugador, numdias=60)

            continue

            if clave in datosJugador:
                ordenDatos = seqDatos if claveSM else datosJugador['OrdenPartidos']
                ordenDatos = seqDatos

                datosAmostrar = datosJugador[clave]

                print(datosComunes['cabeceraLinea'][jug])
                # comentarios = datosJugador['ResumenPartido']
                haJugado = datosJugador['haJugado']
                esLocal = datosJugador['esLocal']
                victoria = datosJugador['haGanado']
                # jornada = datosJugador['Jornada']
                # ordenParts = datosJugador['OrdenPartidos']
                # fechaSTR = [strftime(FORMATOfecha,x) if x else "-" for x in datosJugador['FechaHora']]
                # form = [ calculaFormato(v, l, j, valorDecimal) for (v,l,j) in zip(victoria, esLocal, haJugado)]
                # cv = zip(seqDatos, esLocal, victoria, jornada, haJugado, ordenParts, fechaSTR, datosAmostrar, form)
                # print('##', 'esLocal', 'victoria', 'jornada', 'haJugado', 'ordenParts', 'fecha',
                # 'datosAmostrar','form')
                # print("\n".join(map(lambda x:"%2i %7s %8s %7s %8s %10s %10s %s %s" % x,cv)))
                print(list(zip(cabJornadas, datosAmostrar)), "\n\n")
                # print(ordenDatos)

                for i in ordenDatos:
                    f = "nulo"
                    valor = ""
                    if claveSM and datosAmostrar[i] is None:
                        pass
                    elif claveSM and (i + ot < 0):  # Es la J0 de mercado
                        f = "nulo"
                        valor = datosAmostrar[i]
                    else:
                        # haJugado[i + ot] is not None:
                        f = calculaFormato(victoria[i + ot], esLocal[i + ot], haJugado[i + ot], valorDecimal)
                        valor = datosAmostrar[i]  # if haJugado[i + ot] else ""

                    ws.write(fila, columna, valor, formatos[f])
                    columna += 1

            fila += 1
            columna = 0
            # break

    def addMetadata(workbook, datos):
        ws = workbook.add_worksheet("Metadata")
        fila = 0
        columna = 0
        for l in datos:
            ws.write(fila, columna, l)
            fila += 1

    metadata = ["Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, supermanager.timestamp),
                "Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp),
                "Ejecutado en %s" % strftime(FORMATOtimestamp, gmtime())]

    datosComunes = preparaDatosComunes(jugData)

    # print(jugData)

    # print(datosComunes)

    # print(DumpDict(datosComunes['cabeceraLinea'], datosComunes['claves']))

    wb = Workbook(filename=nomFichero)
    formatos = preparaFormatos(wb)
    # '+/-', 'A', 'BP', 'BR', 'C', 'CODequipo', 'CODrival', 'FP-C', 'FP-F', 'FechaHora',
    # 'Jornada', 'M', 'OrdenPartidos', 'P', 'Partido', 'R-D', 'R-O', 'REB-T', 'ResumenPartido', 'Segs',
    # 'T1%', 'T1-C', 'T1-I', 'T2%', 'T2-C', 'T2-I', 'T3%', 'T3-C', 'T3-I', 'TAP-C', 'TAP-F', 'URL', 'V',
    # 'equipo', 'esLocal', 'haGanado', 'haJugado', 'lesion', 'nombre', 'precio', 'prom3Jornadas', 'promVal',
    # 'rival', 'titular', 'valJornada'
    creaHoja(wb, "ValoracionSM", "valJornada", jugData, datosComunes, formatos, nombreJornadas,
             valorDecimal=True, claveSM=True)
    creaHoja(wb, "Valoracion", "V", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False,
             claveSM=False)
    creaHoja(wb, "PrecioSM", "precio", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=True,
             claveSM=True)
    creaHoja(wb, "PromValSM", "promVal", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=True,
             claveSM=True)
    creaHoja(wb, "prom3J", "prom3Jornadas", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=True,
             claveSM=True)
    creaHoja(wb, "Puntos", "P", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False, claveSM=False)
    creaHoja(wb, "Rebotes", "REB-T", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False,
             claveSM=False)
    creaHoja(wb, "Asistencias", "A", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False,
             claveSM=False)
    creaHoja(wb, "Triples", "T3-C", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False,
             claveSM=False)

    addMetadata(wb, metadata)

    wb.close()

    # jugOrdenados = [clave[0] for clave in
    # list(map(lambda x:(x,jugData['I-precio']), jugData)).sort(reverse=True,itemgetter=lambda y:y[1])]
    # print(jugOrdenados)
    # print(DumpDict(datosCabecera))
    # print(metadata)


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
        partIDX = [i for i in range(len(haJugado)) if haJugado[i] is not None and
                   mktime(fecha[i]) > time() - (numdias * 24 * 3600)]
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

    if 'infile' in args and args.infile:
        sm.loadData(args.infile)
        print("Cargados datos SuperManager de %s" % strftime(FORMATOtimestamp, sm.timestamp))

    temporada = None
    if 'temporada' in args and args.temporada:
        temporada = TemporadaACB()
        temporada.cargaTemporada(args.temporada)
        print("Cargada información de temporada de %s" % strftime(FORMATOtimestamp, temporada.timestamp))

    preparaExcel(sm, temporada)

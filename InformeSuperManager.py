#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import defaultdict
from time import gmtime, strftime

from configargparse import ArgumentParser
from xlsxwriter import Workbook

from SMACB.PartidoACB import PartidoACB
from SMACB.SMconstants import POSICIONES
from SMACB.SuperManager import SuperManagerACB
from SMACB.TemporadaACB import TemporadaACB
from Utils.Misc import CuentaClaves, FORMATOtimestamp


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


def preparaExcel(supermanager, temporada, nomFichero="/tmp/SM.xlsx",):

    jugSM = supermanager.extraeDatosJugadores()
    jugTM = temporada.extraeDatosJugadores()
    jugData = mezclaJugadores(jugTM, jugSM)
    numJornadas = temporada.maxJornada()
    nombreJornadas = {False: temporada.Calendario.nombresJornada()[:numJornadas],
                      True: ['J 0'] + temporada.Calendario.nombresJornada()[:numJornadas]}

    def preparaFormatos(workbook):
        resultado = dict()

        resultado['cabecera'] = workbook.add_format({'bold': True, 'align': 'center'})
        resultado['nulo'] = workbook.add_format()

        resultado['VL'] = workbook.add_format({'bold': True, 'bg_color': 'green'})
        resultado['DL'] = workbook.add_format({'bg_color': 'green'})
        resultado['VF'] = workbook.add_format({'bold': True, 'bg_color': 'blue'})
        resultado['DF'] = workbook.add_format({'bg_color': 'blue'})

        resultado['VLd'] = workbook.add_format({'bold': True, 'bg_color': 'green', 'num_format': '#,##0_;[Red]-#,##0'})
        resultado['DLd'] = workbook.add_format({'bg_color': 'green', 'num_format': '#,##0_;[Red]-#,##0'})
        resultado['VFd'] = workbook.add_format({'bold': True, 'bg_color': 'blue', 'num_format': '#,##0_;[Red]-#,##0'})
        resultado['DFd'] = workbook.add_format({'bg_color': 'blue', 'num_format': '#,##0_;[Red]-#,##0'})

        return resultado

    def calculaFormato(victoria, local, vdecimal):
        resultado = ""
        resultado += "V" if victoria else "D"
        resultado += "L" if local else "F"
        if vdecimal:
            resultado += "d"

        return resultado

    def creaHoja(workbook, nombre, clave, datosJugadores, datosComunes, formatos,
                 nombreJornadas, valorDecimal=False, claveSM=True):
        clavesExistentes = CuentaClaves(datosJugadores)
        # print(clavesExistentes)

        if clave not in clavesExistentes:
            return

        seqDatos = list(range(numJornadas + (1 if claveSM else 0)))
        cabJornadas = nombreJornadas[claveSM]
        ot = -1 if claveSM else 0

        print(ot, seqDatos, cabJornadas)

        ws = workbook.add_worksheet(nombre)

        fila, columna = 0, 0

        ws.write_row(fila, columna, datosComunes['titularCabecera'], formatos['cabecera'])
        columna += len(datosComunes['titularCabecera']) + 1
        ws.write_row(fila, columna, cabJornadas, formatos['cabecera'])
        fila += 1
        columna = 0

        for jug in datosComunes['claves']:
            ws.write_row(fila, columna, datosComunes['cabeceraLinea'][jug])
            columna += len(datosComunes['titularCabecera']) + 1
            datosJugador = datosJugadores[jug]

            if clave in datosJugador:
                datosAmostrar = datosJugador[clave]
                print(datosComunes['cabeceraLinea'][jug], datosAmostrar)
                comentarios = datosJugador['ResumenPartido']
                haJugado = datosJugador['haJugado']
                esLocal = datosJugador['esLocal']
                victoria = datosJugador['haGanado']

                ordenDatos = seqDatos if claveSM else datosJugador['OrdenPartidos']
                print(ordenDatos)

                for i in ordenDatos:
                    if datosAmostrar[i] is not None:
                        if i + ot >= 0:
                            f = calculaFormato(victoria[i + ot], esLocal[i + ot], valorDecimal)
                            valor = datosAmostrar[i] if haJugado[i + ot] else ""
                            if comentarios[i + ot]:
                                print(comentarios[i + ot], valor)
                            #    ws.write_comment(fila, columna, comentarios[i + ot])

                        else:
                            valor = datosAmostrar[i]
                            f = "nulo"
                        print(fila, columna, valor, f)
                        ws.write(fila, columna, valor, formatos[f])

                    columna += 1

            fila += 1
            columna = 0

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

    creaHoja(wb, "ValoracionSM", "valJornada", jugData, datosComunes, formatos,
             nombreJornadas, valorDecimal=True, claveSM=True)
    creaHoja(wb, "Valoracion", "V", jugData, datosComunes, formatos, nombreJornadas, valorDecimal=False, claveSM=False)


#     ws = wb.add_worksheet(name="Valoracion")
#
#     fila = 0
#     columna = 0
#
#     ws.write_row(fila, columna, datosComunes['titularCabecera'])
#     fila += 1
#
#     for jug in datosComunes['claves']:
#         ws.write_row(fila, columna, datosComunes['cabeceraLinea'][jug])
#         fila += 1
#
#     ws.autofilter(0, 0, fila, len(datosComunes['titularCabecera']))

    addMetadata(wb, metadata)

    wb.close()

    # jugOrdenados = [clave[0] for clave in
    # list(map(lambda x:(x,jugData['I-precio']), jugData)).sort(reverse=True,itemgetter=lambda y:y[1])]
    # print(jugOrdenados)
    # print(DumpDict(datosCabecera))
    # print(metadata)


if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add('-v', dest='verbose', action="count", env_var='SM_VERBOSE', required=False, default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='SM_DEBUG', required=False, default=False)

    parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', required=True)
    parser.add('-t', dest='temporada', type=str, env_var='SM_TEMPORADA', required=True)

    parser.add('-o', dest='outfile', type=str, env_var='SM_OUTFILE', required=False)

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

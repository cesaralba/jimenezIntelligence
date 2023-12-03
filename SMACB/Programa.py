import sys
from _operator import itemgetter
from collections import defaultdict
from copy import copy
from math import isnan

import numpy as np
import pandas as pd
from fontTools.otlLib.builder import PairPosBuilder
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle, Table, Paragraph, NextPageTemplate, PageBreak, Spacer
from scipy import stats

from SMACB.Constants import LocalVisitante, haGanado2esp, MARCADORESCLASIF, DESCENSOS
from SMACB.FichaJugador import TRADPOSICION
from SMACB.PartidoACB import PartidoACB
from SMACB.TemporadaACB import TemporadaACB, extraeCampoYorden, auxEtiqPartido, equipo2clasif, \
    precalculaOrdenEstadsLiga, COLSESTADSASCENDING
from Utils.FechaHora import NEVER, Time2Str
from Utils.Misc import onlySetElement, listize

estadGlobales = None
estadGlobalesOrden = None
clasifLiga = None
ESTILOS = getSampleStyleSheet()

FMTECHACORTA = "%d-%m"
DEFTABVALUE = "-"

ESTAD_MEDIA = 0
ESTAD_MEDIANA = 1
ESTAD_DEVSTD = 2
ESTAD_MAX = 3
ESTAD_MIN = 4
ESTAD_COUNT = 5
ESTAD_SUMA = 6

ESTADISTICOEQ = 'mean'
ESTADISTICOJUG = 'mean'

FORMATOCAMPOS = {'entero': {'numero': '{:3.0f}'}, 'float': {'numero': '{:4.1f}'}, }
COLS_IDENTIFIC_JUG = ['competicion', 'temporada', 'CODequipo', 'IDequipo', 'codigo', 'dorsal', 'nombre']

ANCHOTIROS = 16
ANCHOREBOTES = 14


def GENERADORETTIRO(*kargs, **kwargs):
    return lambda f: auxEtiqTiros(f, *kargs, **kwargs)


def GENERADORETREBOTE(*kargs, **kwargs):
    return lambda f: auxEtiqRebotes(f, *kargs, **kwargs)


def GENERADORFECHA(*kargs, **kwargs):
    return lambda f: auxEtFecha(f, *kargs, **kwargs)


def GENERADORTIEMPO(*kargs, **kwargs):
    return lambda f: auxEtiqTiempo(f, *kargs, **kwargs)


def GENMAPDICT(*kargs, **kwargs):
    return lambda f: auxMapDict(f, *kargs, **kwargs)


def GENERADORCLAVEDORSAL(*kargs, **kwargs):
    return lambda f: auxKeyDorsal(f, *kargs, **kwargs)


INFOESTADSEQ = {('Eq', 'P'): {'etiq': 'PF', 'formato': 'float'}, ('Rival', 'P'): {'etiq': 'PC', 'formato': 'float'},
                ('Eq', 'POS'): {'etiq': 'Pos', 'formato': 'float'}, ('Eq', 'OER'): {'etiq': 'OER', 'formato': 'float'},
                ('Rival', 'OER'): {'etiq': 'DER', 'formato': 'float'},
                ('Eq', 'T2'): {'etiq': 'T2', 'generador': GENERADORETTIRO(tiro='2', entero=False, orden=True)},
                ('Eq', 'T3'): {'etiq': 'T3', 'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Eq', 'TC'): {'etiq': 'TC', 'generador': GENERADORETTIRO(tiro='C', entero=False, orden=True)},
                ('Eq', 'ppTC'): {'etiq': 'P / TC-I', 'formato': 'float'},
                ('PTC/PTCPot'): {'etiq': '%PPot', 'formato': 'float'},
                ('Eq', 't3/tc-I'): {'etiq': 'T3-I / TC-I', 'formato': 'float'},
                ('Eq', 'FP-F'): {'etiq': 'F com', 'formato': 'float'},
                ('Eq', 'FP-C'): {'etiq': 'F rec', 'formato': 'float'},
                ('Eq', 'T1'): {'etiq': 'T3', 'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Eq', 'REB'): {'etiq': 'Rebs', 'ancho': 17, 'generador': GENERADORETREBOTE(entero=False, orden=True)},
                ('Eq', 'EffRebD'): {'etiq': 'F rec', 'formato': 'float'},
                ('Eq', 'EffRebO'): {'etiq': 'F rec', 'formato': 'float'}, ('Eq', 'A'): {'formato': 'float'},
                ('Eq', 'BP'): {'formato': 'float'}, ('Eq', 'BR'): {'formato': 'float'},
                ('Eq', 'A/BP'): {'formato': 'float'}, ('Eq', 'A/TC-C'): {'etiq': 'A/Can', 'formato': 'float'},
                ('Eq', 'PNR'): {'formato': 'float'},

                ('Rival', 'T2'): {'generador': GENERADORETTIRO(tiro='2', entero=False, orden=True)},
                ('Rival', 'T3'): {'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'TC'): {'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'ppTC'): {'etiq': 'P / TC-I', 'formato': 'float'},
                ('Rival', 't3/tc-I'): {'etiq': 'T3-I / TC-I', 'formato': 'float'},
                ('Rival', 'T1'): {'etiq': 'TL', 'generador': GENERADORETTIRO(tiro='3', entero=False, orden=True)},
                ('Rival', 'REB'): {'etiq': 'Rebs', 'ancho': 17,
                                   'generador': GENERADORETREBOTE(entero=False, orden=True)},
                ('Rival', 'A'): {'formato': 'float'}, ('Rival', 'BP'): {'formato': 'float'},
                ('Rival', 'BR'): {'formato': 'float'}, ('Rival', 'A/BP'): {'formato': 'float'},
                ('Rival', 'A/TC-C'): {'etiq': 'A/Can', 'formato': 'float'}, ('Rival', 'PNR'): {'formato': 'float'}, }

INFOTABLAJUGS = {('Jugador', 'dorsal'): {'etiq': 'D', 'ancho': 3},
                 ('Jugador', 'Kdorsal'): {'etiq': 'kD', 'generador': GENERADORCLAVEDORSAL(col='dorsal')},
                 ('Jugador', 'nombre'): {'etiq': 'Nombre', 'ancho': 22, 'alignment': 'LEFT'},
                 ('Jugador', 'pos'): {'etiq': 'Pos', 'ancho': 4, 'alignment': 'CENTER'},
                 ('Jugador', 'altura'): {'etiq': 'Alt', 'ancho': 5},
                 ('Jugador', 'licencia'): {'etiq': 'Lic', 'ancho': 5, 'alignment': 'CENTER'},
                 ('Jugador', 'etNac'): {'etiq': 'Nac', 'ancho': 5, 'alignment': 'CENTER',
                                        'generador': GENERADORFECHA(col='fechaNac', formato='%Y')},
                 ('Jugador', 'Activo'): {'etiq': 'Act', 'ancho': 4, 'alignment': 'CENTER',
                                         'generador': GENMAPDICT(col='Activo', lookup={True: 'A', False: 'B'})},
                 ('Trayectoria', 'Acta'): {'etiq': 'Cv', 'ancho': 3, 'formato': 'entero'},
                 ('Trayectoria', 'Jugados'): {'etiq': 'Ju', 'ancho': 3, 'formato': 'entero'},
                 ('Trayectoria', 'Titular'): {'etiq': 'Tt', 'ancho': 3, 'formato': 'entero'},
                 ('Trayectoria', 'Vict'): {'etiq': 'Vc', 'ancho': 3, 'formato': 'entero'},

                 ('Promedios', 'etSegs'): {'etiq': 'Min', 'ancho': 7, 'generador': GENERADORTIEMPO(col='Segs')},
                 ('Promedios', 'P'): {'etiq': 'P', 'ancho': 7, 'formato': 'float'},
                 ('Promedios', 'etiqT2'): {'etiq': 'T2', 'ancho': ANCHOTIROS,
                                           'generador': GENERADORETTIRO('2', entero=False)},
                 ('Promedios', 'etiqT3'): {'etiq': 'T3', 'ancho': ANCHOTIROS,
                                           'generador': GENERADORETTIRO(tiro='3', entero=False)},
                 ('Promedios', 'etiqTC'): {'etiq': 'TC', 'ancho': ANCHOTIROS, 'generador': GENERADORETTIRO('C', False)},
                 ('Promedios', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'etiqT1'): {'etiq': 'TL', 'ancho': ANCHOTIROS, 'generador': GENERADORETTIRO('1', False)},
                 ('Promedios', 'etRebs'): {'etiq': 'Rebs', 'ancho': ANCHOREBOTES,
                                           'generador': GENERADORETREBOTE(entero=False)},
                 ('Promedios', 'A'): {'etiq': 'A', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'BP'): {'etiq': 'BP', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'BR'): {'etiq': 'BR', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'TAP-F'): {'etiq': 'Tap', 'ancho': 6, 'formato': 'float'},
                 ('Promedios', 'TAP-C'): {'etiq': 'Tp R', 'ancho': 6, 'formato': 'float'},

                 ('Totales', 'etSegs'): {'etiq': 'Min', 'ancho': 8, 'generador': GENERADORTIEMPO(col='Segs')},
                 ('Totales', 'P'): {'etiq': 'P', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'etiqT2'): {'etiq': 'T2', 'ancho': ANCHOTIROS,
                                         'generador': GENERADORETTIRO('2', entero=True)},
                 ('Totales', 'etiqT3'): {'etiq': 'T3', 'ancho': ANCHOTIROS,
                                         'generador': GENERADORETTIRO('3', entero=True)},
                 ('Totales', 'etiqTC'): {'etiq': 'TC', 'ancho': ANCHOTIROS,
                                         'generador': GENERADORETTIRO('C', entero=True)},
                 ('Totales', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
                 ('Totales', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'etiqT1'): {'etiq': 'TL', 'ancho': ANCHOTIROS,
                                         'generador': GENERADORETTIRO('1', entero=True)},
                 ('Totales', 'etRebs'): {'etiq': 'Rebs', 'ancho': ANCHOREBOTES,
                                         'generador': GENERADORETREBOTE(entero=True)},
                 ('Totales', 'A'): {'etiq': 'A', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'BP'): {'etiq': 'BP', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'BR'): {'etiq': 'BR', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'TAP-F'): {'etiq': 'Tap', 'ancho': 6, 'formato': 'entero'},
                 ('Totales', 'TAP-C'): {'etiq': 'Tp R', 'ancho': 6, 'formato': 'entero'},

                 ('UltimoPart', 'etFecha'): {'etiq': 'Fecha', 'ancho': 6,
                                             'generador': GENERADORFECHA(col='fechaPartido'), 'alignment': 'CENTER'},
                 ('UltimoPart', 'Partido'): {'etiq': 'Rival', 'ancho': 22, 'alignment': 'LEFT'},
                 ('UltimoPart', 'resultado'): {'etiq': 'Vc', 'ancho': 3, 'alignment': 'CENTER'},
                 ('UltimoPart', 'titular'): {'etiq': 'Tt', 'ancho': 3, 'alignment': 'CENTER'},
                 ('UltimoPart', 'etSegs'): {'etiq': 'Min', 'ancho': 6, 'generador': GENERADORTIEMPO(col='Segs')},
                 ('UltimoPart', 'P'): {'etiq': 'P', 'ancho': 4, 'formato': 'entero'},
                 ('UltimoPart', 'etiqT2'): {'etiq': 'T2', 'ancho': 14, 'generador': GENERADORETTIRO('2', entero=True)},
                 ('UltimoPart', 'etiqT3'): {'etiq': 'T3', 'ancho': 14, 'generador': GENERADORETTIRO('3', entero=True)},
                 ('UltimoPart', 'etiqTC'): {'etiq': 'TC', 'ancho': 14, 'generador': GENERADORETTIRO('C', entero=True)},
                 ('UltimoPart', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
                 ('UltimoPart', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'entero'},
                 ('UltimoPart', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'entero'},
                 ('UltimoPart', 'etiqT1'): {'etiq': 'TL', 'ancho': 14, 'generador': GENERADORETTIRO('1', entero=True)},
                 ('UltimoPart', 'etRebs'): {'etiq': 'Rebs', 'ancho': 10, 'generador': GENERADORETREBOTE(entero=True)},
                 ('UltimoPart', 'A'): {'etiq': 'A', 'ancho': 4, 'formato': 'entero'},
                 ('UltimoPart', 'BP'): {'etiq': 'BP', 'ancho': 4, 'formato': 'entero'},
                 ('UltimoPart', 'BR'): {'etiq': 'BR', 'ancho': 4, 'formato': 'entero'},
                 ('UltimoPart', 'TAP-C'): {'etiq': 'Tap', 'ancho': 4, 'formato': 'entero'},
                 ('UltimoPart', 'TAP-F'): {'etiq': 'Tp R', 'ancho': 4, 'formato': 'entero'}, }


def auxCalculaBalanceStr(record: dict, addPendientes: bool = False, currJornada: int = None, addPendJornada: bool = False) -> str:
    textoAux = ""
    if currJornada is not None:
        pendJornada = currJornada not in record['Jjug']
        pendientes = any([(p not in record['Jjug']) for p in range(1,currJornada)])
        adelantados = any([p > currJornada for p in record['Jjug']])
        textoAux = ""+("J" if (pendJornada and addPendJornada) else "")+ ("P" if pendientes else "")+("A" if adelantados else "")

    strPendiente = f" ({textoAux})" if (addPendientes and textoAux) else ""
    victorias = record.get('V', 0)
    derrotas = record.get('D', 0)
    texto = f"{victorias}-{derrotas}{strPendiente}"

    return texto


def auxEtiqRebotes(df, entero: bool = True) -> str:
    if isnan(df['R-D']):
        return "-"

    formato = "{:3}+{:3} {:3}" if entero else "{:5.1f}+{:5.1f} {:5.1f}"

    valores = [int(v) if entero else v for v in [df['R-D'], df['R-O'], df['REB-T']]]

    result = formato.format(*valores)

    return result


def auxEtiqTiempo(df, col='Segs'):
    t = df[col]
    if isnan(t):
        return "-"

    mins = t // 60
    segs = t % 60

    result = f"{mins:.0f}:{segs:02.0f}"

    return result


def auxEtiqTiros(df, tiro, entero=True):
    formato = "{:3}/{:3} {:5.1f}%" if entero else "{:5.1f}/{:5.1f} {:5.1f}%"

    etTC = f"T{tiro}-C"
    etTI = f"T{tiro}-I"
    etTpc = f"T{tiro}%"

    if df[etTI] == 0.0 or isnan(df[etTI]):
        return "-"

    valores = [int(v) if entero else v for v in [df[etTC], df[etTI]]] + [df[etTpc]]

    result = formato.format(*valores)

    return result


def auxEtFecha(f, col, formato=FMTECHACORTA):
    if f is None:
        return "-"

    dato = f[col]
    result = "-" if pd.isnull(dato) else dato.strftime(formato)

    return result


def auxMapDict(f, col, lookup):
    if f is None:
        return "-"

    dato = f[col]
    result = lookup.get(dato, "-")

    return result


def auxKeyDorsal(f, col):
    if f is None:
        return "-"

    dato = f[col]
    result = -1 if dato == "00" else int(dato)

    return result


def auxGeneraTabla(dfDatos: pd.DataFrame, infoTabla: dict, colSpecs: dict, estiloTablaBaseOps, formatos=None,
                   charWidth=10.0, **kwargs):
    dfColList = []
    filaCab = []
    anchoCols = []
    tStyle = TableStyle(estiloTablaBaseOps)

    for col in infoTabla.get('extraCols', []):
        level, colkey = col
        colSpec = colSpecs.get(col, {})
        newCol = dfDatos[level].apply(colSpec['generador'], axis=1) if 'generador' in colSpec else dfDatos[[col]]
        dfDatos[col] = newCol

    for col, value in infoTabla.get('filtro', []):
        dfDatos = dfDatos.loc[dfDatos[col] == value]

    sortOrder = infoTabla.get('ordena', [])
    byList = [c for c, _ in sortOrder if c in dfDatos.columns]
    ascList = [a for c, a in sortOrder if c in dfDatos.columns]

    dfDatos = dfDatos.sort_values(by=byList, ascending=ascList)

    collist = infoTabla['columnas']

    if formatos is None:
        formatos = dict()

    for i, colkey in enumerate(collist):
        level, etiq = colkey
        colSpec = colSpecs.get(colkey, {})
        newCol = dfDatos[level].apply(colSpec['generador'], axis=1) if 'generador' in colSpec else dfDatos[[colkey]]

        defValue = colSpec.get('default', DEFTABVALUE)
        nullValues = newCol.isnull()

        if 'formato' in colSpec:
            etiqFormato = colSpec['formato']
            if etiqFormato not in formatos:
                raise KeyError(
                    f"auxGeneraTabla: columna '{colkey}': formato '{etiqFormato}' desconocido. " + f"Formatos conocidos: {formatos}")
            formatSpec = formatos[etiqFormato]

            if 'numero' in formatSpec:
                newCol = newCol.apply(lambda c, spec=formatSpec: c.map(spec['numero'].format))
        newEtiq = colSpec.get('etiq', etiq)

        newAncho = colSpec.get('ancho', 10) * charWidth

        # Fills with default value
        finalCol = newCol.copy()
        finalCol[nullValues] = defValue

        dfColList.append(finalCol)
        filaCab.append(newEtiq)
        anchoCols.append(newAncho)
        if 'alignment' in colSpec:
            newCmdStyle = ["ALIGN", (i, 1), (i, -1), colSpec['alignment']]
            tStyle.add(*newCmdStyle)

    datosAux = pd.concat(dfColList, axis=1, join='outer', names=filaCab)

    datosTabla = [filaCab] + datosAux.to_records(index=False, column_dtypes='object').tolist()

    t = Table(datosTabla, style=tStyle, colWidths=anchoCols, **kwargs)

    return t


def datosEstadsEquipoPortada(tempData: TemporadaACB, abrev: str):
    recuperaEstadsGlobales(tempData)

    targAbrev = list(tempData.Calendario.abrevsEquipo(abrev).intersection(estadGlobales.index))[0]
    if not targAbrev:
        valCorrectos = ", ".join(sorted(estadGlobales.index))
        raise KeyError(f"extraeCampoYorden: equipo (abr) '{abrev}' desconocido. Equipos validos: {valCorrectos}")

    estadsEq = estadGlobales.loc[targAbrev]
    estadsEqOrden = estadGlobalesOrden.loc[targAbrev]

    pFav, pFavOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'P', ESTADISTICOEQ)
    pCon, pConOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'P', ESTADISTICOEQ)

    pos, posOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'POS', ESTADISTICOEQ)
    OER, OEROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'OER', ESTADISTICOEQ)
    OERpot, OERpotOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'OERpot', ESTADISTICOEQ)
    DER, DEROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'OER', ESTADISTICOEQ)

    T2C, T2COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2-C', ESTADISTICOEQ)
    T2I, T2IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2-I', ESTADISTICOEQ)
    T2pc, T2pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2%', ESTADISTICOEQ)
    T3C, T3COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3-C', ESTADISTICOEQ)
    T3I, T3IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3-I', ESTADISTICOEQ)
    T3pc, T3pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3%', ESTADISTICOEQ)
    TCC, TCCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC-C', ESTADISTICOEQ)
    TCI, TCIOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC-I', ESTADISTICOEQ)
    TCpc, TCpcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC%', ESTADISTICOEQ)
    ppTC, ppTCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'ppTC', ESTADISTICOEQ)
    PPOTpc, PPOTpcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'PTC/PTCPot', ESTADISTICOEQ)
    ratT3, ratT3Ord = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 't3/tc-I', ESTADISTICOEQ)
    Fcom, FcomOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'FP-F', ESTADISTICOEQ)
    Frec, FrecOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'FP-F', ESTADISTICOEQ)
    T1C, T1COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1-C', ESTADISTICOEQ)
    T1I, T1IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1-I', ESTADISTICOEQ)
    T1pc, T1pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1%', ESTADISTICOEQ)

    RebD, RebDOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'R-D', ESTADISTICOEQ)
    RebO, RebOOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'R-O', ESTADISTICOEQ)
    RebT, RebTOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'REB-T', ESTADISTICOEQ)
    EffRebD, EffRebDOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'EffRebD', ESTADISTICOEQ)
    EffRebO, EffRebOOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'EffRebO', ESTADISTICOEQ)

    A, AOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'A', ESTADISTICOEQ)
    BP, BPOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'BP', ESTADISTICOEQ)
    BR, BROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'BR', ESTADISTICOEQ)
    ApBP, ApBPOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'A/BP', ESTADISTICOEQ)
    ApTCC, ApTCCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'A/TC-C', ESTADISTICOEQ)
    PNR, PNROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'PNR', ESTADISTICOEQ)

    ### Valores del equipo rival

    rT2C, rT2COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T2-C', ESTADISTICOEQ)
    rT2I, rT2IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T2-I', ESTADISTICOEQ)
    rT2pc, rT2pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T2%', ESTADISTICOEQ)
    rT3C, rT3COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T3-C', ESTADISTICOEQ)
    rT3I, rT3IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T3-I', ESTADISTICOEQ)
    rT3pc, rT3pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T3%', ESTADISTICOEQ)
    rTCC, rTCCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'TC-C', ESTADISTICOEQ)
    rTCI, rTCIOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'TC-I', ESTADISTICOEQ)
    rTCpc, rTCpcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'TC%', ESTADISTICOEQ)
    rppTC, rppTCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'ppTC', ESTADISTICOEQ)
    rPPOTpc, rPPOTpcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'PTC/PTCPot', ESTADISTICOEQ)

    rratT3, rratT3Ord = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 't3/tc-I', ESTADISTICOEQ)
    rT1C, rT1COrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T1-C', ESTADISTICOEQ)
    rT1I, rT1IOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T1-I', ESTADISTICOEQ)
    rT1pc, rT1pcOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'T1%', ESTADISTICOEQ)

    rRebD, rRebDOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'R-D', ESTADISTICOEQ)
    rRebO, rRebOOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'R-O', ESTADISTICOEQ)
    rRebT, rRebTOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'REB-T', ESTADISTICOEQ)

    rA, rAOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'A', ESTADISTICOEQ)
    rBP, rBPOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'BP', ESTADISTICOEQ)
    rBR, rBROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'BR', ESTADISTICOEQ)
    rApBP, rApBPOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'A/BP', ESTADISTICOEQ)
    rApTCC, rApTCCOrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'A/TC-C', ESTADISTICOEQ)
    rPNR, rPNROrd = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'PNR', ESTADISTICOEQ)

    ###

    resultEq = f"""
<b>PF</b>:&nbsp;{pFav:.2f}({pFavOrd:.0f}) <b>/</b> 
<b>PC</b>:&nbsp;{pCon:.2f}({pConOrd:.0f}) <b>/</b>
<b>Pos</b>:&nbsp;{pos:.2f}({posOrd:.0f}) <b>/</b> 
<b>OER</b>:&nbsp;{OER:.2f}({OEROrd:.0f}) <b>/</b> 
<b>DER</b>:&nbsp;{DER:.2f}({DEROrd:.0f}) <b>/</b>
<b>T2</b>:&nbsp;{T2C:.2f}({T2IOrd:.0f})/{T2I:.2f}({T2IOrd:.0f})&nbsp;{T2pc:.2f}%({T2pcOrd:.0f}) <b>/</b> 
<b>T3</b>:&nbsp;{T3C:.2f}({T3IOrd:.0f})/{T3I:.2f}({T3IOrd:.0f})&nbsp;{T3pc:.2f}%({T3pcOrd:.0f}) <b>/</b>
<b>TC</b>:&nbsp;{TCC:.2f}({TCIOrd:.0f})/{TCI:.2f}({TCIOrd:.0f})&nbsp;{TCpc:.2f}%({TCpcOrd:.0f}) <b>/</b> 
<b>P&nbsp;por&nbsp;TC-I</b>:&nbsp;{ppTC:.2f}({ppTCOrd:.0f}) <b>/</b> <b>%PPot</b>:&nbsp;{PPOTpc:.2f}({PPOTpcOrd:.0f}) <b>/</b>  
<b>T3-I/TC-I</b>&nbsp;{ratT3:.2f}%({ratT3Ord:.0f}) <b>/</b>
<b>F&nbsp;com</b>:&nbsp;{Fcom:.2f}({FcomOrd:.0f})  <b>/</b> <b>F&nbsp;rec</b>:&nbsp;{Frec:.2f}({FrecOrd:.0f})  <b>/</b> 
<b>TL</b>:&nbsp;{T1C:.2f}({T1COrd:.0f})/{T1I:.2f}({T1IOrd:.0f})&nbsp;{T1pc:.2f}%({T1pcOrd:.0f}) <b>/</b>
<b>Reb</b>:&nbsp;{RebD:.2f}({RebDOrd:.0f})+{RebO:.2f}({RebOOrd:.0f})&nbsp;{RebT:.2f}({RebTOrd:.0f}) <b>/</b> 
<b>EffRD</b>:&nbsp;{EffRebD:.2f}%({EffRebDOrd:.0f}) <b>EffRO</b>:&nbsp;{EffRebO:.2f}%({EffRebOOrd:.0f}) <b>/</b>
<b>A</b>:&nbsp;{A:.2f}({AOrd:.0f}) <b>/</b> <b>BP</b>:&nbsp;{BP:.2f}({BPOrd:.0f}) <b>/</b> 
<b>BR</b>:&nbsp;{BR:.2f}({BROrd:.0f}) <b>/</b> 
<b>A/BP</b>:&nbsp;{ApBP:.2f}({ApBPOrd:.0f}) <b>/</b> <b>A/Can</b>:&nbsp;{ApTCC:.2f}%({ApTCCOrd:.0f}) <b>/</b>
<b>PNR</b>:&nbsp;{PNR:.2f}({PNROrd:.0f})<br/>

<B>RIVAL</B> 
<b>T2</b>:&nbsp;{rT2C:.2f}({rT2IOrd:.0f})/{rT2I:.2f}({rT2IOrd:.0f})&nbsp;{rT2pc:.2f}%({rT2pcOrd:.0f}) <b>/</b> 
<b>T3</b>:&nbsp;{rT3C:.2f}({rT3IOrd:.0f})/{rT3I:.2f}({rT3IOrd:.0f})&nbsp;{rT3pc:.2f}%({rT3pcOrd:.0f}) <b>/</b>
<b>TC</b>:&nbsp;{rTCC:.2f}({rTCIOrd:.0f})/{rTCI:.2f}({rTCIOrd:.0f})&nbsp;{rTCpc:.2f}%({rTCpcOrd:.0f}) <b>/</b> 
<b>P&nbsp;por&nbsp;TC-I</b>:&nbsp;{rppTC:.2f}({rppTCOrd:.0f}) <b>/</b>  <b>%PPot</b>:&nbsp;{rPPOTpc:.2f}({rPPOTpcOrd:.0f}) <b>/</b>  
<b>T3-I/TC-I</b>&nbsp;{rratT3:.2f}%({rratT3Ord:.0f}) <b>/</b>
<b>TL</b>:&nbsp;{rT1C:.2f}({rT1COrd:.0f})/{rT1I:.2f}({rT1IOrd:.0f})&nbsp;{rT1pc:.2f}%({rT1pcOrd:.0f}) <b>/</b> 
<b>Reb</b>:&nbsp;{rRebD:.2f}({rRebDOrd:.0f})+{rRebO:.2f}({rRebOOrd:.0f})&nbsp;{rRebT:.2f}({rRebTOrd:.0f}) <b>/</b>
<b>A</b>:&nbsp;{rA:.2f}({rAOrd:.0f}) <b>/</b> <b>BP</b>:&nbsp;{rBP:.2f}({rBPOrd:.0f}) <b>/</b> 
<b>BR</b>:&nbsp;{rBR:.2f}({rBROrd:.0f}) <b>/</b> <b>A/BP</b>:&nbsp;{rApBP:.2f}({rApBPOrd:.0f}) <b>/</b> 
<b>A/Can</b>:&nbsp;{rApTCC:.2f}%({rApTCCOrd:.0f}) <b>/</b>
<b>PNR</b>:&nbsp;{rPNR:.2f}({rPNROrd:.0f})
"""

    return resultEq


def estadsEquipoPortada(tempData: TemporadaACB, abrevs: list):
    datLocal = datosEstadsEquipoPortada(tempData, abrevs[0])
    datVisitante = datosEstadsEquipoPortada(tempData, abrevs[1])

    style = ParagraphStyle('Normal', align='left', fontName='Helvetica', fontSize=10, leading=11, )

    parLocal = Paragraph(datLocal, style)
    parVisit = Paragraph(datVisitante, style)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[parLocal, parVisit]], colWidths=[100 * mm, 100 * mm], style=tStyle)

    return t


def estadsEquipoPortada_df(tempData: TemporadaACB, abrevs: list):
    datLocal = datosEstadsEquipoPortada(tempData, abrevs[0])
    datVisitante = datosEstadsEquipoPortada(tempData, abrevs[1])

    style = ParagraphStyle('Normal', align='left', fontName='Helvetica', fontSize=10, leading=11, )

    parLocal = Paragraph(datLocal, style)
    parVisit = Paragraph(datVisitante, style)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[parLocal, parVisit]], colWidths=[100 * mm, 100 * mm], style=tStyle)

    return t


def datosJugadores(tempData: TemporadaACB, abrEq, partJug):
    COLS_TRAYECT_TEMP_orig_names = ['enActa', 'haJugado', 'esTitular', 'haGanado', ]
    COLS_TRAYECT_TEMP_orig = [(col, 'sum') for col in COLS_TRAYECT_TEMP_orig_names]
    COLS_TRAYECT_TEMP = ['Acta', 'Jugados', 'Titular', 'Vict']
    COLS_FICHA = ['id', 'alias', 'pos', 'altura', 'licencia', 'fechaNac']
    VALS_ESTAD_JUGADOR = ['A', 'BP', 'BR', 'FP-C', 'FP-F', 'P', 'ppTC', 'R-D', 'R-O', 'REB-T', 'Segs', 'T1-C', 'T1-I',
                          'T1%', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-I', 'TC-C', 'TC%', 'PTC', 'TAP-C',
                          'TAP-F']

    COLS_ESTAD_PROM = [(col, ESTADISTICOJUG) for col in VALS_ESTAD_JUGADOR]
    COLS_ESTAD_TOTAL = [(col, 'sum') for col in VALS_ESTAD_JUGADOR]

    abrevsEq = tempData.Calendario.abrevsEquipo(abrEq)

    urlPartsJug = [p.url for p in partJug]

    auxDF = tempData.extraeDataframeJugadores(listaURLPartidos=urlPartsJug)

    jugDF = auxDF.loc[auxDF['CODequipo'].isin(abrevsEq)]

    estadsJugDF = tempData.dfEstadsJugadores(jugDF, abrEq=abrEq)
    fichasJugadores = tempData.dataFrameFichasJugadores()
    fichasJugadores.posicion = fichasJugadores.posicion.map(TRADPOSICION)

    trayectTemp = estadsJugDF[COLS_TRAYECT_TEMP_orig]
    trayectTemp.columns = pd.Index(COLS_TRAYECT_TEMP)

    identifJug = pd.concat([estadsJugDF['Jugador'][COLS_IDENTIFIC_JUG], fichasJugadores[COLS_FICHA]], axis=1,
                           join="inner")

    if tempData.descargaPlantillas:
        idEq = onlySetElement(tempData.Calendario.tradEquipos['c2i'][abrEq])
        statusJugs = tempData.plantillas[idEq].jugadores.extractKey('activo', False)
        identifJug['Activo'] = identifJug['codigo'].map(statusJugs, 'ignore')
    else:
        identifJug['Activo'] = True

    estadsPromedios = estadsJugDF[COLS_ESTAD_PROM].droplevel(1, axis=1)
    estadsTotales = estadsJugDF[COLS_ESTAD_TOTAL].droplevel(1, axis=1)
    datosUltPart = jugDF.sort_values('fechaPartido').groupby('codigo').tail(n=1).set_index('codigo', drop=False)
    datosUltPart['Partido'] = datosUltPart.apply(
        lambda p: auxEtiqPartido(tempData, p['CODrival'], esLocal=p['esLocal']), axis=1)

    dataFramesAJuntar = {'Jugador': identifJug, 'Trayectoria': trayectTemp, 'Promedios': estadsPromedios,
                         # .drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP)
                         'Totales': estadsTotales,  # .drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP)
                         'UltimoPart': datosUltPart}  # .drop(columns=COLS_IDENTIFIC_JUG)
    result = pd.concat(dataFramesAJuntar.values(), axis=1, join='outer', keys=dataFramesAJuntar.keys())

    return result


def datosTablaLiga(tempData: TemporadaACB, currJornada: int=None):
    """
    Calcula los datos que rellenarán la tabla de liga así como las posiciones de los partidos jugados y pendientes para
    darles formato
    :param tempData: Info completa de la temporada
    :param currJornada: Jornada a la que se refiere el programa
    :return: listaListasCeldas,tupla de listas de coords de jugados y pendientes, primer eq con balance negativo
    List
    """
    firstNegBal = None

    recuperaClasifLiga(tempData)
    FONTSIZE = 10
    CELLPAD = 3 * mm

    estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                              alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
    ESTILOS.add(estCelda)

    # Precalcula el contenido de la tabla
    auxTabla = defaultdict(dict)
    auxTablaJuPe = {'pe': [], 'ju': []}

    for jId, jDatos in tempData.Calendario.Jornadas.items():
        for part in jDatos['partidos']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part
            auxTablaJuPe['ju'].append((idLocal, idVisitante))

        for part in jDatos['pendientes']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part
            auxTablaJuPe['pe'].append((idLocal, idVisitante))

    # En la clasificación está el contenido de los márgenes, de las diagonales y el orden de presentación
    # de los equipos
    seqIDs = [(pos, list(equipo['idEq'])[0]) for pos, equipo in enumerate(clasifLiga)]

    datosTabla = []
    id2pos = dict()

    cabFila = [Paragraph('<b>Casa/Fuera</b>', style=estCelda)] + [
        Paragraph('<b>' + list(clasifLiga[pos]['abrevsEq'])[0] + '</b>', style=estCelda) for pos, _ in seqIDs] + [
                  Paragraph('<b>Como local</b>', style=estCelda)]
    datosTabla.append(cabFila)

    for pos, idLocal in seqIDs:
        datosEq = clasifLiga[pos]

        id2pos[idLocal] = pos
        fila = []
        nombreCorto = sorted(datosEq['nombresEq'], key=lambda n: len(n))[0]
        abrev = list(datosEq['abrevsEq'])[0]
        fila.append(Paragraph(f"{nombreCorto} (<b>{abrev}</b>)", style=estCelda))
        for _, idVisit in seqIDs:
            if idLocal != idVisit:  # Partido, la otra se usa para poner el balance
                part = auxTabla[idLocal][idVisit]

                fechaAux = part.get('fechaPartido', NEVER)

                fecha = 'TBD' if (fechaAux == NEVER) else fechaAux.strftime(FMTECHACORTA)
                jornada = part['jornada']

                texto = f"J:{jornada}<br/>@{fecha}"
                if not part['pendiente']:
                    pLocal = part['equipos']['Local']['puntos']
                    pVisit = part['equipos']['Visitante']['puntos']
                    texto = f"J:{jornada}<br/><b>{pLocal}-{pVisit}</b>"
            else:
                auxTexto = auxCalculaBalanceStr(datosEq, addPendientes=True, currJornada=currJornada,addPendJornada=True)
                texto = f"<b>{auxTexto}</b>"
            fila.append(Paragraph(texto, style=estCelda))

        if (datosEq['V'] < datosEq['D']) and (firstNegBal is None):
            firstNegBal = pos

        fila.append(Paragraph(auxCalculaBalanceStr(datosEq['CasaFuera']['Local']), style=estCelda))
        datosTabla.append(fila)

    filaBalFuera = [Paragraph('<b>Como visitante</b>', style=estCelda)]
    for pos, idLocal in seqIDs:
        filaBalFuera.append(Paragraph(auxCalculaBalanceStr(clasifLiga[pos]['CasaFuera']['Visitante']), style=estCelda))
    filaBalFuera.append([])
    datosTabla.append(filaBalFuera)

    coordsPeJu = {tipoPart: [(id2pos[idLocal], id2pos[idVisitante]) for idLocal, idVisitante in listaTipo] for
                  tipoPart, listaTipo in auxTablaJuPe.items()}

    return datosTabla, coordsPeJu, firstNegBal


def listaEquipos(tempData, beQuiet=False):
    if beQuiet:
        print(" ".join(sorted(tempData.Calendario.tradEquipos['c2n'])))
    else:
        print("Abreviatura -> nombre(s) equipo")
        for abr in sorted(tempData.Calendario.tradEquipos['c2n']):
            listaEquiposAux = sorted(tempData.Calendario.tradEquipos['c2n'][abr], key=lambda x: (len(x), x),
                                     reverse=True)
            listaEquiposStr = ",".join(listaEquiposAux)
            print(f'{abr}: {listaEquiposStr}')

    sys.exit(0)


def datosMezclaPartJugados(tempData, abrevs, partsIzda, partsDcha):
    partsIzdaAux = copy(partsIzda)
    partsDchaAux = copy(partsDcha)
    lineas = list()

    abrIzda, abrDcha = abrevs
    abrevsIzda = tempData.Calendario.abrevsEquipo(abrIzda)
    abrevsDcha = tempData.Calendario.abrevsEquipo(abrDcha)
    abrevsPartido = set().union(abrevsIzda).union(abrevsDcha)

    while (len(partsIzdaAux) + len(partsDchaAux)) > 0:
        bloque = dict()

        try:
            priPartIzda = partsIzdaAux[0]
        except IndexError:
            bloque['J'] = partsDchaAux[0]['jornada']
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
            lineas.append(bloque)
            continue

        try:
            priPartDcha = partsDchaAux[0]
        except IndexError:
            bloque['J'] = priPartIzda['jornada']
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            lineas.append(bloque)
            continue

        bloque = dict()
        if priPartIzda['jornada'] == priPartDcha['jornada']:
            bloque['J'] = priPartIzda['jornada']
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
            abrevsPartIzda = priPartIzda.CodigosCalendario if isinstance(priPartIzda, PartidoACB) else priPartIzda[
                'loc2abrev']

            bloque['precedente'] = (len(abrevsPartido.intersection(abrevsPartIzda.values())) == 2)

        else:
            if (priPartIzda['fechaPartido'], priPartIzda['jornada']) < (
                    priPartDcha['fechaPartido'], priPartDcha['jornada']):
                bloque['J'] = priPartIzda['jornada']
                bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            else:
                bloque['J'] = priPartDcha['jornada']
                bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)

        lineas.append(bloque)

    return lineas


def paginasJugadores(tempData, abrEqs, juIzda, juDcha):
    result = []

    if len(juIzda):
        datosIzda = datosJugadores(tempData, abrEqs[0], juIzda)
        tablasJugadIzda = tablasJugadoresEquipo(datosIzda)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (infoTabla, t) in tablasJugadIzda:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(t)
            result.append(NextPageTemplate('apaisada'))

    if len(juDcha):
        datosIzda = datosJugadores(tempData, abrEqs[1], juDcha)
        tablasJugadIzda = tablasJugadoresEquipo(datosIzda)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (infoTabla, t) in tablasJugadIzda:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(NextPageTemplate('apaisada'))
            result.append(t)

    return result


def partidoTrayectoria(partido, abrevs, datosTemp):
    # Cadena de información del partido

    datosPartido = partido.DatosSuministrados if isinstance(partido, PartidoACB) else partido

    datoFecha = partido.fechaPartido if isinstance(partido, PartidoACB) else datosPartido['fechaPartido']

    strFecha = datoFecha.strftime(FMTECHACORTA) if datoFecha != NEVER else "TBD"
    abrEq = list(abrevs.intersection(datosPartido['participantes']))[0]
    abrRival = list(datosPartido['participantes'].difference(abrevs))[0]
    locEq = datosPartido['abrev2loc'][abrEq]
    textRival = auxEtiqPartido(datosTemp, abrRival, locEq=locEq, usaLargo=False)
    strRival = f"{strFecha}: {textRival}"

    strResultado = None
    if isinstance(partido, PartidoACB):
        # Ya ha habido partido por lo que podemos calcular trayectoria anterior y resultado
        clasifAux = datosTemp.clasifEquipo(abrRival, partido['fechaPartido'])
        clasifStr = auxCalculaBalanceStr(clasifAux,addPendientes=True,currJornada=int(partido['jornada']),addPendJornada=False)
        strRival = f"{strFecha}: {textRival} ({clasifStr})"
        marcador = {loc: str(partido.DatosSuministrados['resultado'][loc]) for loc in LocalVisitante}
        for loc in LocalVisitante:
            if partido.DatosSuministrados['equipos'][loc]['haGanado']:
                marcador[loc] = "<b>{}</b>".format(marcador[loc])
            if loc == locEq:
                marcador[loc] = "<u>{}</u>".format(marcador[loc])

        resAux = [marcador[loc] for loc in LocalVisitante]

        strResultado = "{} ({})".format("-".join(resAux), haGanado2esp[datosPartido['equipos'][locEq]['haGanado']])

    return strRival, strResultado


def reportTrayectoriaEquipos(tempData, abrEqs, juIzda, juDcha, peIzda, peDcha):
    CELLPAD = 0.15 * mm
    FONTSIZE = 9

    filasPrecedentes = set()

    listaTrayectoria = datosMezclaPartJugados(tempData, abrEqs, juIzda, juDcha)
    listaFuturos = datosMezclaPartJugados(tempData, abrEqs, peIzda, peDcha)

    filas = []

    resultStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE, align='center')
    cellStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE)
    jornStyle = ParagraphStyle('trayStyle', fontName='Helvetica-Bold', fontSize=FONTSIZE + 1, align='right')

    for i, f in enumerate(listaTrayectoria):
        datosIzda = f.get('izda', ['', ''])
        datosDcha = f.get('dcha', ['', ''])
        jornada = f['J']
        if f.get('precedente', False):
            filasPrecedentes.add(i)

        aux = [Paragraph(f"<para align='center'>{datosIzda[1]}</para>"), Paragraph(f"<para>{datosIzda[0]}</para>"),
               Paragraph(f"<para align='center' fontName='Helvetica-Bold'>{str(jornada)}</para>"),
               Paragraph(f"<para>{datosDcha[0]}</para>"), Paragraph(f"<para align='center'>{datosDcha[1]}</para>")]
        filas.append(aux)
    for i, f in enumerate(listaFuturos, start=len(listaTrayectoria)):
        datosIzda, _ = f.get('izda', ['', None])
        datosDcha, _ = f.get('dcha', ['', None])
        jornada = f['J']
        if f.get('precedente', False):
            if i == 0:  # Es el partido que vamos a tratar, no tiene sentido incluirlo
                continue
            filasPrecedentes.add(i)

        aux = [Paragraph(f"<para>{datosIzda}</para>"), None,
               Paragraph(f"<para align='center' fontName='Helvetica-Bold'>{str(jornada)}</para>"),
               Paragraph(f"<para>{datosDcha}</para>"), None]
        filas.append(aux)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1), ])

    # Formatos extra a la tabla
    if len(listaTrayectoria) and len(listaFuturos):
        tStyle.add("LINEABOVE", (0, len(listaTrayectoria)), (-1, len(listaTrayectoria)), 1 * mm, colors.black)
    for fNum in filasPrecedentes:
        tStyle.add("BACKGROUND", (0, fNum), (-1, fNum), colors.lightgrey)
    for fNum, _ in enumerate(listaFuturos, start=len(listaTrayectoria)):
        tStyle.add("SPAN", (0, fNum), (1, fNum))
        tStyle.add("SPAN", (-2, fNum), (-1, fNum))

    ANCHORESULTADO = (FONTSIZE * 0.6) * 13
    ANCHOETPARTIDO = (FONTSIZE * 0.6) * 32
    ANCHOJORNADA = ((FONTSIZE + 1) * 0.6) * 4

    t = Table(data=filas, style=tStyle,
              colWidths=[ANCHORESULTADO, ANCHOETPARTIDO, ANCHOJORNADA, ANCHOETPARTIDO, ANCHORESULTADO],
              rowHeights=FONTSIZE + 4)

    return t


def tablasJugadoresEquipo(jugDF):
    result = []

    CELLPAD = 0.2 * mm
    FONTSIZE = 8
    ANCHOLETRA = FONTSIZE * 0.5
    COLACTIVO = ('Jugador', 'Activo')
    COLDORSAL_IDX = ('Jugador', 'Kdorsal')
    COLSIDENT_PROM = [('Jugador', 'dorsal'), ('Jugador', 'nombre'), ('Trayectoria', 'Acta'), ('Trayectoria', 'Jugados'),
                      ('Trayectoria', 'Titular'), ('Trayectoria', 'Vict')]
    COLSIDENT_TOT = [('Jugador', 'dorsal'), COLACTIVO, ('Jugador', 'nombre'), ('Trayectoria', 'Acta'),
                     ('Trayectoria', 'Jugados'), ('Trayectoria', 'Titular'), ('Trayectoria', 'Vict')]
    COLSIDENT_UP = [('Jugador', 'dorsal'), ('Jugador', 'nombre'), ('Jugador', 'pos'), ('Jugador', 'altura'),
                    ('Jugador', 'licencia'), ('Jugador', 'etNac')]

    COLS_PROMED = [('Promedios', 'etSegs'), ('Promedios', 'P'), ('Promedios', 'etiqT2'), ('Promedios', 'etiqT3'),
                   ('Promedios', 'etiqTC'), ('Promedios', 'ppTC'), ('Promedios', 'FP-F'), ('Promedios', 'FP-C'),
                   ('Promedios', 'etiqT1'), ('Promedios', 'etRebs'), ('Promedios', 'A'), ('Promedios', 'BP'),
                   ('Promedios', 'BR'), ('Promedios', 'TAP-F'), ('Promedios', 'TAP-C'), ]
    COLS_TOTALES = [('Totales', 'etSegs'), ('Totales', 'P'), ('Totales', 'etiqT2'), ('Totales', 'etiqT3'),
                    ('Totales', 'etiqTC'), ('Totales', 'ppTC'), ('Totales', 'FP-F'), ('Totales', 'FP-C'),
                    ('Totales', 'etiqT1'), ('Totales', 'etRebs'), ('Totales', 'A'), ('Totales', 'BP'),
                    ('Totales', 'BR'), ('Totales', 'TAP-F'), ('Totales', 'TAP-C'), ]
    COLS_ULTP = [('UltimoPart', 'etFecha'), ('UltimoPart', 'Partido'), ('UltimoPart', 'resultado'),
                 ('UltimoPart', 'titular'), ('UltimoPart', 'etSegs'), ('UltimoPart', 'P'), ('UltimoPart', 'etiqT2'),
                 ('UltimoPart', 'etiqT3'), ('UltimoPart', 'etiqTC'), ('UltimoPart', 'ppTC'), ('UltimoPart', 'FP-F'),
                 ('UltimoPart', 'FP-C'), ('UltimoPart', 'etiqT1'), ('UltimoPart', 'etRebs'), ('UltimoPart', 'A'),
                 ('UltimoPart', 'BP'), ('UltimoPart', 'BR'), ('UltimoPart', 'TAP-F'), ('UltimoPart', 'TAP-C'), ]

    baseOPS = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
               ('ALIGN', (0, 0), (-1, 0), 'CENTER'), ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
               ('ALIGN', (0, 1), (-1, -1), 'RIGHT'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
               ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1),
               ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
               ('TOPPADDING', (0, 0), (-1, -1), CELLPAD), ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD), ]

    tablas = {'promedios': {'seq': 1, 'nombre': 'Promedios', 'columnas': (COLSIDENT_PROM + COLS_PROMED),
                            'extraCols': [('Jugador', 'Kdorsal')], 'filtro': [(COLACTIVO, True)],
                            'ordena': [(COLDORSAL_IDX, True)]},
              'totales': {'seq': 2, 'nombre': 'Totales', 'columnas': (COLSIDENT_TOT + COLS_TOTALES),
                          'extraCols': [('Jugador', 'Kdorsal')], 'ordena': [(COLACTIVO, False), (COLDORSAL_IDX, True)]},
              'ultimo': {'seq': 3, 'nombre': 'Último partido', 'columnas': (COLSIDENT_UP + COLS_ULTP),
                         'extraCols': [('Jugador', 'Kdorsal')], 'filtro': [(COLACTIVO, True)],
                         'ordena': [(COLDORSAL_IDX, True)]}}
    auxDF = jugDF.copy()

    for infoTabla in tablas.values():  # , [COLSIDENT +COLS_TOTALES], [COLSIDENT +COLS_ULTP]
        t = auxGeneraTabla(auxDF, infoTabla, INFOTABLAJUGS, baseOPS, FORMATOCAMPOS, ANCHOLETRA, repeatRows=1)

        result.append((infoTabla, t))

    return result


def tablaLiga(tempData: TemporadaACB, equiposAmarcar=None,currJornada:int=None):
    CELLPAD = 0.3 * mm
    FONTSIZE = 9

    datosAux, coordsJuPe, firstNegBal = datosTablaLiga(tempData, currJornada)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                         ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (0, 0), (-1, -1), FONTSIZE),
                         ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
                         ('TOPPADDING', (0, 0), (-1, -1), CELLPAD), ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD),
                         ("BACKGROUND", (-1, 1), (-1, -2), colors.lightgrey),
                         ("BACKGROUND", (1, -1), (-2, -1), colors.lightgrey)])
    alturas = [20] + [29] * (len(datosAux) - 2) + [22]
    anchos = [61] + [39] * (len(datosAux) - 2) + [38]

    CANTGREYBAL = .70
    colBal = colors.rgb2cmyk(CANTGREYBAL, CANTGREYBAL, CANTGREYBAL)

    for i in range(1, len(datosAux) - 1):
        tStyle.add("BACKGROUND", (i, i), (i, i), colBal)

    ANCHOMARCAPOS = 2
    for pos in MARCADORESCLASIF:
        commH, commV = ("LINEBELOW", "LINEAFTER") if pos >= 0 else ("LINEABOVE", "LINEBEFORE")
        incr = 0 if pos >= 0 else -1
        posIni = 0 if pos >= 0 else pos + incr
        posFin = pos + incr if pos >= 0 else -1
        tStyle.add(commH, (posIni, pos + incr), (posFin, pos + incr), ANCHOMARCAPOS, colors.black)
        tStyle.add(commV, (pos + incr, posIni), (pos + incr, posFin), ANCHOMARCAPOS, colors.black)

    # Equipos para descenso (horizontal)
    tStyle.add("LINEBEFORE", (-DESCENSOS - 1, 0), (-DESCENSOS - 1, 0), ANCHOMARCAPOS, colors.black)
    tStyle.add("LINEBEFORE", (-1, 0), (-1, 0), ANCHOMARCAPOS, colors.black)
    tStyle.add("LINEBELOW", (-DESCENSOS - 1, 0), (-2, 0), ANCHOMARCAPOS, colors.black)

    # Equipos para descenso (vertical)
    tStyle.add("LINEAFTER", (0, -DESCENSOS - 1), (0, -2), ANCHOMARCAPOS, colors.black)
    tStyle.add("LINEABOVE", (0, -DESCENSOS - 1), (0, -DESCENSOS - 1), ANCHOMARCAPOS, colors.black)
    tStyle.add("LINEABOVE", (0, -1), (0, -1), ANCHOMARCAPOS, colors.black)

    # Balance negativo
    if firstNegBal is not None:
        tStyle.add("LINEAFTER", (firstNegBal, 0), (firstNegBal, firstNegBal), ANCHOMARCAPOS, colors.black, "squared",
                   (1, 8))
        tStyle.add("LINEBELOW", (0, firstNegBal), (firstNegBal, firstNegBal), ANCHOMARCAPOS, colors.black, "squared",
                   (1, 8))

    # Marca la clase
    claveJuPe = 'ju' if len(coordsJuPe['ju']) <= len(coordsJuPe['pe']) else 'pe'
    CANTGREYJUPE = .90
    colP = colors.rgb2cmyk(CANTGREYJUPE, CANTGREYJUPE, CANTGREYJUPE)
    for x, y in coordsJuPe[claveJuPe]:
        coord = (y + 1, x + 1)
        tStyle.add("BACKGROUND", coord, coord, colP)

    if equiposAmarcar is not None:
        CANTGREYEQ = .80
        colEq = colors.rgb2cmyk(CANTGREYEQ, CANTGREYEQ, CANTGREYEQ)

        parEqs = set(listize(equiposAmarcar))
        seqIDs = [(pos, equipo['abrevsEq']) for pos, equipo in enumerate(clasifLiga) if
                  equipo['abrevsEq'].intersection(parEqs)]

        for pos, _ in seqIDs:
            tStyle.add("BACKGROUND", (pos + 1, 0), (pos + 1, 0), colEq)
            tStyle.add("BACKGROUND", (0, pos + 1), (0, pos + 1), colEq)

    t = Table(datosAux, style=tStyle, rowHeights=alturas, colWidths=anchos)

    return t


def cabeceraPortada(partido, tempData):
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = Time2Str(partido['fechaPartido'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - " + f"J: <b>{j}</b><br/>{fh}</para>",
        style)

    cabLocal = datosCabEquipo(datosLocal, tempData, partido['fechaPartido'],currJornada=int(j))
    cabVisit = datosCabEquipo(datosVisit, tempData, partido['fechaPartido'],currJornada=int(j))

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def datosCabEquipo(datosEq, tempData, fecha,currJornada:int=None):
    recuperaClasifLiga(tempData, fecha)

    # TODO: Imagen (descargar imagen de escudo y plantarla)
    nombre = datosEq['nombcorto']

    clasifAux = equipo2clasif(clasifLiga, datosEq['abrev'])
    clasifStr = auxCalculaBalanceStr(clasifAux,addPendientes=True,currJornada=currJornada)

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def recuperaEstadsGlobales(tempData):
    global estadGlobales
    global estadGlobalesOrden
    if estadGlobales is None:
        estadGlobales = tempData.dfEstadsLiga()
        estadGlobalesOrden = precalculaOrdenEstadsLiga(estadGlobales, COLSESTADSASCENDING)


def recuperaClasifLiga(tempData: TemporadaACB, fecha=None):
    global clasifLiga

    if clasifLiga is None:
        clasifLiga = tempData.clasifLiga(fecha)


def datosRestoJornada(tempData: TemporadaACB, datosSig: tuple):
    """
    Devuelve la lista de partidos de la jornada a la que corresponde  el partidos siguiente del equipo objetivo
    :param tempData: datos descargados de ACB (ya cargados, no el fichero)
    :param datosSig: resultado de tempData.sigPartido (info sobre el siguiente partido del equipo objetivo
    :return: lista con información sobre partidos sacada del Calendario
    """
    result = list()
    sigPartido = datosSig[0]
    jornada = int(sigPartido['jornada'])
    calJornada = tempData.Calendario.Jornadas[jornada]

    for p in calJornada['partidos']:
        urlPart = p['url']
        part = tempData.Partidos[urlPart]
        data = copy(p)
        data['fechaPartido'] = part.fechaPartido
        result.append(data)

    result.extend([p for p in calJornada['pendientes'] if p['participantes'] != sigPartido['participantes']])
    result.sort(key=itemgetter('fechaPartido'))

    return result


def tablaRestoJornada(tempData: TemporadaACB, datosSig: tuple):
    def infoEq(eqData: dict, jornada:int):
        abrev = eqData['abrev']

        clasifAux = equipo2clasif(clasifLiga, abrev)
        clasifStr = auxCalculaBalanceStr(clasifAux,addPendientes=True,currJornada=jornada,addPendJornada=False)
        formatoIn, formatoOut = ('<b>', '</b>') if eqData['haGanado'] else ('', '')
        formato = "{fIn}{nombre}{fOut} [{balance}]"
        result = formato.format(nombre=eqData['nombcorto'], balance=clasifStr, fIn=formatoIn, fOut=formatoOut)
        return result

    def infoRes(partData: dict):
        pts = list()
        for loc in LocalVisitante:
            p = partData['resultado'][loc]
            formato = ("<b>{:3}</b>" if partData['equipos'][loc]['haGanado'] else "{:3}")
            pts.append(formato.format(p))
        result = "-".join(pts)
        return result

    def etFecha(tStamp: pd.Timestamp, fechaRef: pd.Timestamp = None):
        tFormato = "%d-%m-%Y"
        if fechaRef and abs((tStamp - fechaRef).days) <= 3:
            tFormato = "%a %m@%H:%M"
        result = tStamp.strftime(tFormato)
        return result

    def preparaDatos(datos, tstampRef):
        intData = list()
        for p in sorted(datos, key=itemgetter('fechaPartido')):
            info = {'pendiente': p['pendiente'], 'fecha': etFecha(p['fechaPartido'], tstampRef)}
            for loc in LocalVisitante:
                info[loc] = infoEq(p['equipos'][loc],jornada=jornada)
            if not p['pendiente']:
                info['resultado'] = infoRes(p)

            intData.append(info)
        return intData

    # Data preparation
    sigPartido = datosSig[0]
    jornada = int(sigPartido['jornada'])
    recuperaClasifLiga(tempData)
    drj = datosRestoJornada(tempData, datosSig)
    datosParts = preparaDatos(drj, sigPartido['fechaPartido'])

    if len(datosParts) == 0:
        return None
    # Table building
    textoCab = f"<b>Resto jornada {jornada}</b>"
    filaCab = [Paragraph(f"<para align='center'>{textoCab}</para>"), None, None]
    filas = [filaCab]

    for part in datosParts:
        datosIzq = part['Local']
        datosDcha = part['Visitante']
        datosCentr = part['fecha'] if part['pendiente'] else part['resultado']

        aux = [Paragraph(f"<para align='left'>{datosIzq}</para>"),
               Paragraph(f"<para align='center'>{datosCentr}</para>"),
               Paragraph(f"<para align='right'>{datosDcha}</para>")]
        filas.append(aux)

    FONTSIZE = 9

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1), ("SPAN", (0, 0), (-1, 0))])

    ANCHOEQUIPO = (FONTSIZE * 0.6) * 24
    ANCHOCENTRO = ((FONTSIZE + 1) * 0.6) * 14
    t = Table(data=filas, style=tStyle, colWidths=[ANCHOEQUIPO, ANCHOCENTRO, ANCHOEQUIPO], rowHeights=FONTSIZE + 4)

    return t


def tablasClasifLiga(tempData: TemporadaACB):
    def datosTablaClasif(clasif: list):
        result = list()
        for pos, eq in enumerate(clasif):
            nombEq = sorted(eq['nombresEq'], key=lambda n: len(n))[0]
            victs = eq.get('V', 0)
            derrs = eq.get('D', 0)
            jugs = victs + derrs
            ratio = (100.0 * victs / jugs) if (jugs != 0) else 0.0
            puntF = eq.get('Pfav', 0)
            puntC = eq.get('Pcon', 0)
            diffP = puntF - puntC

            fila = [Paragraph(f"<para align='right'>{pos + 1}</para>"),
                    Paragraph(f"<para align='left'>{nombEq}</para>"), Paragraph(f"<para align='right'>{jugs}</para>"),
                    Paragraph(f"<para align='center'>{victs:2}-{derrs:2}</para>"),
                    Paragraph(f"<para align='right'>{ratio:3.0f}%</para>"),
                    Paragraph(f"<para align='right'>{puntF}</para>"), Paragraph(f"<para align='right'>{puntC}</para>"),
                    Paragraph(f"<para align='right'>{diffP}</para>")]
            result.append(fila)
        return result

    def firstBalNeg(clasif: list):
        for pos,eq in enumerate(clasif):
            victs = eq.get('V', 0)
            derrs = eq.get('D', 0)

            if derrs > victs:
                return pos+1
        return None

    recuperaClasifLiga(tempData)
    filasClasLiga = datosTablaClasif(clasifLiga)

    filaCab = [Paragraph("<para align='center'><b>Po</b></para>"),
        Paragraph("<para align='center'><b>Equipo</b></para>"), Paragraph("<para align='center'><b>J</b></para>"),
        Paragraph("<para align='center'><b>V-D</b></para>"), Paragraph("<para align='center'><b>%</b></para>"),
        Paragraph("<para align='center'><b>PF</b></para>"), Paragraph("<para align='center'><b>PC</b></para>"),
        Paragraph("<para align='center'><b>Df</b></para>")]

    lista1 = [filaCab] + filasClasLiga

    # for eqIDX in range(9):
    #     lista1.append(filasClasLiga[eqIDX])
    #     lista2.append(filasClasLiga[9+eqIDX])

    FONTSIZE = 8

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1)])

    ANCHOPOS = (FONTSIZE * 0.6) * 5.3
    ANCHOEQUIPO = (FONTSIZE * 0.6) * 19
    ANCHOPARTS = (FONTSIZE * 0.6) * 4.9
    ANCHOPERC = (FONTSIZE * 0.6) * 7
    ANCHOPUNTS = (FONTSIZE * 0.6) * 6.8


    ANCHOMARCAPOS = 2
    for pos in MARCADORESCLASIF:
        commH = "LINEBELOW"
        incr = 0 if pos >= 0 else -1
        tStyle.add(commH, (0, pos + incr), (-1 , pos + incr), ANCHOMARCAPOS, colors.black)

    # Balance negativo
    posFirstNegBal = firstBalNeg(clasifLiga)
    if posFirstNegBal is not None:
        tStyle.add("LINEABOVE", (0, posFirstNegBal), (-1, posFirstNegBal), ANCHOMARCAPOS, colors.black, "squared",
                   (1, 8))

    tabla1 = Table(data=lista1, style=tStyle,
                   colWidths=[ANCHOPOS, ANCHOEQUIPO, ANCHOPARTS, ANCHOPARTS * 1.4, ANCHOPERC, ANCHOPUNTS, ANCHOPUNTS,
                              ANCHOPUNTS], rowHeights=FONTSIZE + 4)

    return tabla1

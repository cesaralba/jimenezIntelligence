import sys
from _operator import itemgetter
from collections import defaultdict, namedtuple
from copy import copy
from itertools import product
from math import isnan
from time import gmtime, strftime
from typing import Iterable, Optional

import pandas as pd
from CAPcore.Misc import listize, onlySetElement
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import NextPageTemplate, PageBreak, Paragraph, Spacer, Table, TableStyle

import SMACB.TemporadaACB as TempACB
from .Constants import (CATESTADSEQ2IGNORE, CATESTADSEQASCENDING, DEFAULTNUMFORMAT, DESCENSOS, filaTrayectoriaEq,
                             haGanado2esp, infoClasifEquipo, infoSigPartido, local2espLargo, LocalVisitante,
                             MARCADORESCLASIF, RANKFORMAT, REPORTLEYENDAS, TRADPOSICION, )
from .TemporadaACB import (auxEtiqPartido, calculaEstadsYOrdenLiga, equipo2clasif, esEstCreciente,
                                extraeCampoYorden, TemporadaACB, )
from Utils.FechaHora import NEVER, secs2TimeStr, time2Str
from Utils.ReportLab.RLverticalText import VerticalParagraph

# Variables globales
estadGlobales: Optional[pd.DataFrame] = None
estadGlobalesOrden: Optional[pd.DataFrame] = None
allMagnsInEstads: Optional[set] = None
clasifLiga: Optional[list] = None
numEqs: Optional[int] = None
mitadEqs: Optional[int] = None
tradEquipos: Optional[dict] = {'a2n': defaultdict(str), 'n2a': defaultdict(str), 'i2a': defaultdict(str)}

ESTILOS = getSampleStyleSheet()

CANTGREYEQ = .80
colEq = colors.rgb2cmyk(CANTGREYEQ, CANTGREYEQ, CANTGREYEQ)

FMTECHACORTA = "%d-%m"
DEFTABVALUE = "-"
filaComparEstadistica = namedtuple('filaComparEstadistica',
                                   ['magn', 'isAscending', 'locAbr', 'locMagn', 'locRank', 'locHigh', 'maxMagn',
                                    'maxAbr', 'maxHigh', 'ligaMed', 'ligaStd', 'minMagn', 'minAbr', 'minHigh', 'visAbr',
                                    'visMagn', 'visRank', 'visHigh', 'nombreMagn', 'formatoMagn', 'leyenda'])

filaTablaClasif = namedtuple('filaTablaClasif',
                             ['posic', 'nombre', 'jugs', 'victs', 'derrs', 'ratio', 'puntF', 'puntC', 'diffP',
                              'resalta'])
tuplaMaxMinMagn = namedtuple('tuplaMaxMinMagn',
                             ['minVal', 'minEtq', 'minAbrevs', 'maxVal', 'maxEtq', 'maxAbrevs', 'abrevs2add'])

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
                ('Eq', 'PTC/PTCPot'): {'etiq': '%PPot', 'formato': 'float'},
                ('Eq', 't3/tc-I'): {'etiq': 'T3-I / TC-I', 'formato': 'float'},
                ('Eq', 'FP-F'): {'etiq': 'F com', 'formato': 'float'},
                ('Eq', 'FP-C'): {'etiq': 'F rec', 'formato': 'float'},
                ('Eq', 'T1'): {'etiq': 'T1', 'generador': GENERADORETTIRO(tiro='1', entero=False, orden=True)},
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
                ('Rival', 'PTC/PTCPot'): {'etiq': '%PPot', 'formato': 'float'},
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
                 ('Totales', 'A-BP'): {'etiq': 'A/BP', 'ancho': 6, 'formato': 'float'},
                 ('Totales', 'A-TCI'): {'etiq': 'A/TC', 'ancho': 6, 'formato': 'float'},
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


def auxCalculaBalanceStrSuf(record: infoClasifEquipo, addPendientes: bool = False, currJornada: int = None,
                            addPendJornada: bool = False
                            ) -> str:
    textoAux = ""
    if currJornada is not None:
        pendJornada = currJornada not in record.Jjug
        pendientes = [p for p in range(1, currJornada) if p not in record.Jjug]
        adelantados = [p for p in record.Jjug if p > currJornada]
        textoAux = ("" + ("J" if (pendJornada and addPendJornada) else "") + ("P" if pendientes else "") + (
            "A" if adelantados else ""))

    strPendiente = f" ({textoAux})" if (addPendientes and textoAux) else ""

    return strPendiente


def auxCalculaBalanceStr(record: infoClasifEquipo, addPendientes: bool = False, currJornada: int = None,
                         addPendJornada: bool = False
                         ) -> str:
    strPendiente = auxCalculaBalanceStrSuf(record, addPendientes, currJornada, addPendJornada)
    victorias = record.V
    derrotas = record.D
    texto = f"{victorias}-{derrotas}{strPendiente}"

    return texto


def auxCalculaFirstBalNeg(clasif: list[infoClasifEquipo]):
    for posic, eq in enumerate(clasif):
        victs = eq.V
        derrs = eq.D

        if derrs > victs:
            return posic + 1
    return None


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

    return secs2TimeStr(t)


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


def auxFilasTablaEstadisticos(datosAmostrar: dict, clavesEquipo: list | None = None, clavesRival: list | None = None,
                              estiloCelda: ParagraphStyle = None, estiloCabCelda: ParagraphStyle = None
                              ) -> (list, dict):
    result = list()
    leyendas = dict()
    leyendasFlag = False

    auxClEq = clavesEquipo
    auxClRiv = clavesRival if clavesRival else auxClEq

    listaClaves = list(product(['Eq'], auxClEq)) + list(product(['Rival'], auxClRiv))
    for clave in listaClaves:
        dato = datosAmostrar[clave]

        auxLocMagn = dato.formatoMagn.format(dato.locMagn)
        valLocRank = RANKFORMAT.format(dato.locRank)
        auxVisMagn = dato.formatoMagn.format(dato.visMagn)
        valVisRank = RANKFORMAT.format(dato.visRank)

        valLocMagn = auxBold(auxLocMagn) if dato.locHigh else auxLocMagn
        valVisMagn = auxBold(auxVisMagn) if dato.visHigh else auxVisMagn

        auxMinMagn = dato.formatoMagn.format(dato.minMagn)
        auxMaxMagn = dato.formatoMagn.format(dato.maxMagn)
        valACBmed = dato.formatoMagn.format(dato.ligaMed)
        valACBstd = dato.formatoMagn.format(dato.ligaStd)
        valMinMagn = auxBold(auxMinMagn) if dato.minHigh else auxMinMagn
        valMaxMagn = auxBold(auxMaxMagn) if dato.maxHigh else auxMaxMagn

        fila = [None, Paragraph(f"[{dato.isAscending}] {auxBold(dato.nombreMagn):s}", style=estiloCabCelda),
                Paragraph(f"{valLocMagn} [{valLocRank}]", style=estiloCelda),
                Paragraph(f"{valVisMagn} [{valVisRank}]", style=estiloCelda),
                Paragraph(f"{valMaxMagn} ({dato.maxAbr:3s})", style=estiloCelda),
                Paragraph(f"{valACBmed}\u00b1{valACBstd}", style=estiloCelda),
                Paragraph(f"{valMinMagn} ({dato.minAbr:3s})", style=estiloCelda)]

        if dato.leyenda:
            leyendas[dato.nombreMagn] = dato.leyenda
            leyendasFlag = True
        else:
            print(f"Warning: '{dato.nombreMagn}' no tiene leyenda ({dato.kMagn})")

        result.append(fila)

    if leyendasFlag:
        for fila in result:
            fila.append([])

    result[0][0] = VerticalParagraph(auxBold("Equipo"))
    result[len(clavesEquipo) - 1][0] = VerticalParagraph(auxBold("Rival"))
    return result, leyendas


def auxFindTargetAbrevs(tempData: TemporadaACB, datosSig: infoSigPartido, ):
    sigPartido = datosSig.sigPartido
    result = {k: list(tempData.Calendario.abrevsEquipo(sigPartido['loc2abrev'][k]).intersection(estadGlobales.index))[0]
              for k in LocalVisitante}

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


def auxBold(data):
    return f"<b>{data}</b>"


def auxGeneraLeyendaEstadsCelda(leyenda: dict, FONTSIZE: int, listaEqs: Iterable):
    legendStyle = ParagraphStyle('tabEstadsLegend', fontSize=FONTSIZE, alignment=TA_JUSTIFY, wordWrap=True,
                                 leading=10, )

    separador = "<center>---</center><br/>"
    textoEncab = ("""
<b>Mejor</b>: Primero en el ranking<br/>    
<b>ACB</b>: Media de la liga (+- desv estándar)<br/>    
<b>Peor</b>: Último en el ranking<br/>    
    """)

    textoEtEqs = ("""
<b>Equipo</b>: Valores conseguidos por el equipo<br/>    
<b>Rival</b>: Valores conseguidos por el rival<br/>
    """)
    textoCD = ("""
<b>[C]</b>: <i>Mejor</i> cuanto menor<br/>    
<b>[D]</b>: <i>Mejor</i> cuanto mayor<br/>
    """)
    textoEstads = "".join(
        [f"<b>{k.replace(' ', '&nbsp;')}</b>:&nbsp;{leyenda[k]}<br/>" for k in sorted(leyenda.keys())])

    textoEqs = "".join(
        [f"<b>{abr.replace(' ', '&nbsp;')}</b>:&nbsp;{tradEquipos['a2n'][abr]}<br/>" for abr in sorted(listaEqs)])

    textoCompleto = separador.join([textoEtEqs, textoCD, textoEncab, textoEstads, textoEqs])
    result = Paragraph(textoCompleto, style=legendStyle)
    return result


def auxGeneraLeyendaEstadsJugsCelda(leyendaTxt: str):
    legendStyle = ParagraphStyle('tabJugsLegend', alignment=TA_CENTER, allowWidows=0)
    result = VerticalParagraph(leyendaTxt, style=legendStyle)
    return result


def auxGeneraLeyendaLiga():
    texto = ("<b>Leyenda en balance total</b>: <b>A</b>:&nbsp;Partido(s) adelantado(s)<b> J</b>:&nbsp;Jornada actual "
             "pendiente de jugar<b> "
             "P</b>:&nbsp;Partido(s) pendiente(s)")

    FONTSIZE = 8
    legendStyle = ParagraphStyle('tabLigaLegend', fontSize=FONTSIZE, alignment=TA_JUSTIFY, wordWrap=True,
                                 leading=FONTSIZE + 0.5, )
    result = Paragraph(texto, style=legendStyle)

    return result


def auxJugsBajaTablaJugs(datos: pd.DataFrame, colActivo=('Jugador', 'Activo')) -> list[int]:
    """
    Devuelve las filas con jugadores que figuran como dados de baja (para ser más preciso, no como Alta)
    :param datos: dataframe con datos para tabla de jugadores
    :param colActivo: columna que contiene si el jugador está activo
    :return: lista con las filas del dataframe (comienza en 0) con jugadores así
    """
    result = []

    # No hay datos
    if colActivo not in datos.columns:
        return result

    estadoJugs = datos[colActivo]

    # Si son todos de baja, nos da igual señalar
    if all(estadoJugs) or all(estadoJugs == False):
        return result

    result = [i for i, estado in enumerate(list(estadoJugs)) if not estado]

    return result


def auxGeneraTablaJugs(dfDatos: pd.DataFrame, clave: str, infoTabla: dict, colSpecs: dict, estiloTablaBaseOps,
                       formatos=None, charWidth=10.0, **kwargs
                       ):
    dfColList = []
    filaCab = []
    anchoCols = []

    listaEstilo = estiloTablaBaseOps.copy()

    dfDatos[('Global', 'Leyenda')] = ""

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

    abrevStr = ""
    abrevEq = kwargs.get('abrev', None)
    if abrevEq:
        abrevStr = f" ({abrevEq})"
        kwargs.pop('abrev')

    for i, colkey in enumerate([('Global', 'Leyenda')] + collist, start=0):
        level, etiq = colkey
        colSpec = colSpecs.get(colkey, {})
        newCol = dfDatos[level].apply(colSpec['generador'], axis=1) if 'generador' in colSpec else dfDatos[[colkey]]

        defValue = colSpec.get('default', DEFTABVALUE)
        nullValues = newCol.isnull()

        if 'formato' in colSpec:
            etiqFormato = colSpec['formato']
            if etiqFormato not in formatos:
                raise KeyError(f"auxGeneraTablaJugs: columna '{colkey}': formato '{etiqFormato}' desconocido. "
                               f"Formatos conocidos: {formatos}")
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
            listaEstilo.append(newCmdStyle)

    datosAux = pd.concat(dfColList, axis=1, join='outer', names=filaCab)
    datosTabla = [filaCab] + datosAux.to_records(index=False, column_dtypes='object').tolist()

    # Añade leyenda de la tabla
    leyenda = infoTabla.get('nombre', clave) + abrevStr
    anchoCols[0] = 15
    datosTabla[0][0] = auxGeneraLeyendaEstadsJugsCelda(auxBold(leyenda))
    estiloCeldaLeyenda = [('SPAN', (0, 0), (0, -1)), ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
                          ('ALIGN', (0, 0), (0, -1), 'CENTER')]
    listaEstilo.extend(estiloCeldaLeyenda)

    for fila in auxJugsBajaTablaJugs(dfDatos):
        estilo = ('FONT', (1, fila + 1), (-1, fila + 1), 'Helvetica-Oblique')
        listaEstilo.append(estilo)

    tStyle = TableStyle(listaEstilo)
    t = Table(datosTabla, style=tStyle, colWidths=anchoCols, **kwargs)

    return t


def datosEstadsBasicas(tempData: TemporadaACB, infoEq: dict):
    recuperaEstadsGlobales(tempData)

    abrev = infoEq['abrev']
    nombreCorto = infoEq.get('nombcorto', abrev)

    targAbrev = list(tempData.Calendario.abrevsEquipo(abrev).intersection(estadGlobales.index))[0]
    if not targAbrev:
        valCorrectos = ", ".join(sorted(estadGlobales.index))
        raise KeyError(f"extraeCampoYorden: equipo (abr) '{abrev}' desconocido. Equipos validos: {valCorrectos}")

    estadsEq = estadGlobales.loc[targAbrev]
    estadsEqOrden = estadGlobalesOrden.loc[targAbrev]

    pFav, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'P', ESTADISTICOEQ)
    pCon, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'P', ESTADISTICOEQ)

    T2C, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2-C', ESTADISTICOEQ)
    T2I, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2-I', ESTADISTICOEQ)
    T2pc, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T2%', ESTADISTICOEQ)
    T3C, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3-C', ESTADISTICOEQ)
    T3I, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3-I', ESTADISTICOEQ)
    T3pc, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T3%', ESTADISTICOEQ)
    TCC, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC-C', ESTADISTICOEQ)
    TCI, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC-I', ESTADISTICOEQ)
    TCpc, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'TC%', ESTADISTICOEQ)
    T1C, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1-C', ESTADISTICOEQ)
    T1I, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1-I', ESTADISTICOEQ)
    T1pc, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'T1%', ESTADISTICOEQ)

    Fcom, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'FP-F', ESTADISTICOEQ)
    Frec, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Rival', 'FP-F', ESTADISTICOEQ)

    RebD, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'R-D', ESTADISTICOEQ)
    RebO, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'R-O', ESTADISTICOEQ)
    RebT, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'REB-T', ESTADISTICOEQ)

    A, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'A', ESTADISTICOEQ)
    BP, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'BP', ESTADISTICOEQ)
    BR, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'BR', ESTADISTICOEQ)
    PNR, _ = extraeCampoYorden(estadsEq, estadsEqOrden, 'Eq', 'PNR', ESTADISTICOEQ)

    # noqa: E702
    resultEq = (f"<b>{nombreCorto}</b>&nbsp;[{abrev}] "
                f"<b>PF</b>:&nbsp;{pFav:.2f} <b>/</b> <b>PC</b>:&nbsp;{pCon:.2f} <b>/</b> "
                f"<b>T2</b>:&nbsp;{T2C:.2f}/ {T2I:.2f}&nbsp;{T2pc:.2f}% <b>/</b> "
                f"<b>T3</b>:&nbsp;{T3C:.2f}/{T3I:.2f}&nbsp;{T3pc:.2f}% <b>/</b> "
                f"<b>TC</b>:&nbsp;{TCC:.2f}/{TCI:.2f}&nbsp;{TCpc:.2f}% <b>/</b> "
                f"<b>TL</b>:&nbsp;{T1C:.2f}/{T1I:.2f}&nbsp;{T1pc:.2f}% <b>/</b> "
                f"<b>Reb</b>:&nbsp;{RebD:.2f}+{RebO:.2f}&nbsp;{RebT:.2f} <b>/</b> "
                f"<b>A</b>:&nbsp;{A:.2f} <b>/</b> "
                f"<b>BP</b>:&nbsp;{BP:.2f} <b>/</b> <b>PNR</b>:&nbsp;{PNR:.2f} "
                f"<b>/</b> <b>BR</b>:&nbsp;{BR:.2f} "
                f"<b>/</b> <b>F&nbsp;com</b>:&nbsp;{Fcom:.2f}  <b>/</b> <b>F&nbsp;rec</b>:&nbsp;{Frec:.2f}")
    # qa
    return resultEq


def datosJugadores(tempData: TemporadaACB, abrEq, partJug):
    COLS_TRAYECT_TEMP_orig_names = ['enActa', 'haJugado', 'esTitular', 'haGanado', ]
    COLS_TRAYECT_TEMP_orig = [(col, 'sum') for col in COLS_TRAYECT_TEMP_orig_names]
    COLS_TRAYECT_TEMP = ['Acta', 'Jugados', 'Titular', 'Vict']
    COLS_FICHA = ['id', 'alias', 'pos', 'altura', 'licencia', 'fechaNac']
    VALS_ESTAD_JUGADOR = ['A', 'A-BP', 'A-TCI', 'BP', 'BR', 'FP-C', 'FP-F', 'P', 'ppTC', 'R-D', 'R-O', 'REB-T', 'Segs',
                          'T1-C', 'T1-I', 'T1%', 'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-I', 'TC-C', 'TC%',
                          'PTC', 'TAP-C', 'TAP-F']

    COLS_ESTAD_PROM = [(col, ESTADISTICOJUG) for col in VALS_ESTAD_JUGADOR]
    COLS_ESTAD_TOTAL = [(col, 'sum') for col in VALS_ESTAD_JUGADOR]

    abrevsEq = tempData.Calendario.abrevsEquipo(abrEq)

    auxDF = tempData.extraeDataframeJugadores(listaURLPartidos=partJug)

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


def datosTablaLiga(tempData: TemporadaACB, currJornada: int = None):
    """
    Calcula los datos que rellenarán la tabla de liga así como las posiciones de los partidos jugados y pendientes para
    darles formato
    :param tempData: Info completa de la temporada
    :param currJornada: Jornada a la que se refiere el programa
    :return: listaListasCeldas,tupla de listas de coords de jugados y pendientes, primer eq con balance negativo
    List
    """

    muestraJornada = len(tempData.Calendario.Jornadas[currJornada]['partidos']) > 0
    recuperaClasifLiga(tempData)
    firstNegBal = auxCalculaFirstBalNeg(clasifLiga)

    FONTSIZE = 10
    CELLPAD = 3 * mm

    estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                              alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
    ESTILOS.add(estCelda)

    # Precalcula el contenido de la tabla
    auxTabla = defaultdict(dict)
    auxTablaJuPe = {'pe': [], 'ju': []}

    for _, jDatos in tempData.Calendario.Jornadas.items():
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
    seqIDs = [(pos, list(equipo.idEq)[0]) for pos, equipo in enumerate(clasifLiga)]

    datosTabla = []
    id2pos = dict()

    cabFila = [Paragraph('<b>Casa/Fuera</b>', style=estCelda)] + [
        Paragraph('<b>' + list(clasifLiga[pos].abrevsEq)[0] + '</b>', style=estCelda) for pos, _ in seqIDs] + [
                  Paragraph('<b>Como local</b>', style=estCelda)]
    datosTabla.append(cabFila)

    for pos, idLocal in seqIDs:
        datosEq = clasifLiga[pos]

        id2pos[idLocal] = pos
        fila = []
        nombreCorto = datosEq.nombreCorto
        abrev = datosEq.abrevAusar
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
                auxTexto = auxCalculaBalanceStr(datosEq, addPendientes=True, currJornada=currJornada,
                                                addPendJornada=muestraJornada)
                texto = f"<b>{auxTexto}</b>"
            fila.append(Paragraph(texto, style=estCelda))

        fila.append(Paragraph(auxCalculaBalanceStr(datosEq.CasaFuera['Local']), style=estCelda))
        datosTabla.append(fila)

    filaBalFuera = [Paragraph('<b>Como visitante</b>', style=estCelda)]
    for pos, idLocal in seqIDs:
        filaBalFuera.append(Paragraph(auxCalculaBalanceStr(clasifLiga[pos].CasaFuera['Visitante']), style=estCelda))
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


def paginasJugadores(tempData, abrEqs, juLocal, juVisit):
    result = []

    if len(juLocal):
        datosLocal = datosJugadores(tempData, abrEqs[0], juLocal)
        tablasJugadLocal = tablasJugadoresEquipo(datosLocal, abrev=abrEqs[0])

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (infoTabla, t) in tablasJugadLocal:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(t)
            result.append(NextPageTemplate('apaisada'))

    if len(juVisit):
        datosVisit = datosJugadores(tempData, abrEqs[1], juVisit)
        tablasJugadVisit = tablasJugadoresEquipo(datosVisit, abrev=abrEqs[1])

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())

        for (infoTabla, t) in tablasJugadVisit:
            result.append(Spacer(100 * mm, 2 * mm))
            result.append(NextPageTemplate('apaisada'))
            result.append(t)

    return result


def partidoTrayectoria(partido: TempACB.filaTrayectoriaEq, datosTemp: TemporadaACB):
    datoFecha = partido.fechaPartido
    strFecha = partido.fechaPartido.strftime(FMTECHACORTA) if datoFecha != NEVER else "TBD"
    etiqLoc = "vs " if partido.esLocal else "@"
    nombrRival = partido.equipoRival.nombcorto
    abrevRival = partido.equipoRival.abrev
    textRival = f"{etiqLoc}{nombrRival}"
    strRival = f"{strFecha}: {textRival}"

    strResultado = None
    if not partido.pendiente:
        clasifAux = datosTemp.clasifEquipo(abrevRival, datoFecha)
        clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=int(partido.jornada),
                                         addPendJornada=False)
        strRival = f"{strFecha}: {textRival} ({clasifStr})"
        marcador = partido.resultado._asdict()
        locEq = local2espLargo[partido.esLocal]
        locGanador = local2espLargo[partido.esLocal and partido.haGanado]
        for loc in LocalVisitante:
            marcador[loc] = str(marcador[loc])
            if loc == locGanador:
                marcador[loc] = "<b>{}</b>".format(marcador[loc])
            if loc == locEq:
                marcador[loc] = "<u>{}</u>".format(marcador[loc])

        resAux = [marcador[loc] for loc in LocalVisitante]
        strResultado = "{} ({})".format("-".join(resAux), haGanado2esp[partido.haGanado])
    return strRival, strResultado


def reportTrayectoriaEquipos(tempData: TemporadaACB, infoPartido: infoSigPartido):
    sigPartido = infoPartido.sigPartido

    FONTSIZE = 8

    filasPrecedentes = set()
    incrFila = 0
    marcaCurrJornada = None
    mergeIzdaList = list()
    mergeDchaList = list()

    j17izda = None
    j17dcha = None

    trayectoriasCombinadas = tempData.mergeTrayectoriaEquipos(*(tuple(infoPartido.abrevLV)), True, True)

    filasTabla = []

    resultStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE, alignment=TA_CENTER)
    cellStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=FONTSIZE, alignment=TA_LEFT)
    jornStyle = ParagraphStyle('trayStyle', fontName='Helvetica-Bold', fontSize=FONTSIZE + 1, alignment=TA_CENTER)

    def preparaCeldasTrayectoria(data: filaTrayectoriaEq | None, ladoIzdo: bool = False) -> (list, bool):
        merge = False
        if data is None:
            result = [None, None]
            merge = True
        elif data.pendiente:
            etiq, _ = partidoTrayectoria(data, tempData)
            result = [Paragraph(etiq, style=cellStyle), None]
            merge = True
        else:
            etiq, marcador = partidoTrayectoria(data, tempData)
            result = [Paragraph(etiq, style=cellStyle), Paragraph(marcador, style=resultStyle)]
            if ladoIzdo:
                result.reverse()

        return result, merge

    for numFila, fila in enumerate(trayectoriasCombinadas):
        datosIzda = fila.izda
        datosDcha = fila.dcha
        jornada = fila.jornada

        if fila.precedente:
            if fila.jornada == sigPartido['jornada']:
                marcaCurrJornada = numFila
                incrFila = -1
                continue
            else:
                filasPrecedentes.add(numFila + incrFila)

        if fila.jornada == '17':
            if datosIzda and datosIzda.pendiente:
                j17izda = numFila + incrFila
            if datosDcha and datosDcha.pendiente:
                j17dcha = numFila + incrFila

        celdasIzda, mergeIzda = preparaCeldasTrayectoria(datosIzda, True)
        celdasDcha, mergeDcha = preparaCeldasTrayectoria(datosDcha, False)

        if mergeIzda:
            mergeIzdaList.append(numFila + incrFila)
        if mergeDcha:
            mergeDchaList.append(numFila + incrFila)

        celdaJornada = [Paragraph(f"{str(jornada)}", style=jornStyle)]
        aux = celdasIzda + celdaJornada + celdasDcha
        filasTabla.append(aux)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1), ])

    # Formatos extra a la tabla
    if marcaCurrJornada:
        tStyle.add("LINEABOVE", (0, marcaCurrJornada), (-1, marcaCurrJornada), 1 * mm, colors.black)

    if j17izda:
        tStyle.add("LINEBELOW", (0, j17izda), (2, j17izda), 0.75 * mm, colors.black, "squared", (1, 8))
    if j17dcha:
        tStyle.add("LINEBELOW", (-3, j17dcha), (-1, j17dcha), 0.75 * mm, colors.black, "squared", (1, 8))

    for fNum in filasPrecedentes:
        tStyle.add("BACKGROUND", (0, fNum), (-1, fNum), colors.lightgrey)

    for fNum in mergeIzdaList:
        tStyle.add("SPAN", (0, fNum), (1, fNum))
    for fNum in mergeDchaList:
        tStyle.add("SPAN", (-2, fNum), (-1, fNum))

    ANCHORESULTADO = (FONTSIZE * 0.6) * 13
    ANCHOETPARTIDO = (FONTSIZE * 0.6) * 35
    ANCHOJORNADA = ((FONTSIZE + 1) * 0.6) * 5

    ANCHOCOLS = [ANCHORESULTADO, ANCHOETPARTIDO, ANCHOJORNADA, ANCHOETPARTIDO, ANCHORESULTADO]

    t = Table(data=filasTabla, style=tStyle, colWidths=ANCHOCOLS, rowHeights=FONTSIZE + 4.5)

    return t


def tablasJugadoresEquipo(jugDF, abrev: Optional[str] = None):
    result = []

    CELLPAD = 0.5
    FONTSIZE = 8
    ANCHOLETRA = FONTSIZE * 0.5
    COLACTIVO = ('Jugador', 'Activo')
    COLDORSAL_IDX = ('Jugador', 'Kdorsal')
    COLSIDENT_PROM = [('Jugador', 'dorsal'), ('Jugador', 'pos'), ('Jugador', 'nombre'), ('Trayectoria', 'Acta'),
                      ('Trayectoria', 'Jugados'), ('Trayectoria', 'Titular'), ('Trayectoria', 'Vict')]
    COLSIDENT_TOT = [('Jugador', 'dorsal'), COLACTIVO, ('Jugador', 'pos'), ('Jugador', 'nombre'),
                     ('Trayectoria', 'Acta'), ('Trayectoria', 'Jugados'), ('Trayectoria', 'Titular'),
                     ('Trayectoria', 'Vict')]
    COLSIDENT_UP = [('Jugador', 'dorsal'), ('Jugador', 'nombre'), ('Jugador', 'pos'), ('Jugador', 'altura'),
                    ('Jugador', 'licencia'), ('Jugador', 'etNac')]

    COLS_PROMED = [('Promedios', 'etSegs'), ('Promedios', 'P'), ('Promedios', 'etiqT2'), ('Promedios', 'etiqT3'),
                   ('Promedios', 'etiqTC'), ('Promedios', 'ppTC'), ('Promedios', 'FP-F'), ('Promedios', 'FP-C'),
                   ('Promedios', 'etiqT1'), ('Promedios', 'etRebs'), ('Promedios', 'A'), ('Promedios', 'BP'),
                   ('Promedios', 'BR'), ('Promedios', 'TAP-F'), ('Promedios', 'TAP-C'), ]
    COLS_TOTALES = [('Totales', 'etSegs'), ('Totales', 'P'), ('Totales', 'etiqT2'), ('Totales', 'etiqT3'),
                    ('Totales', 'etiqTC'), ('Totales', 'ppTC'), ('Totales', 'FP-F'), ('Totales', 'FP-C'),
                    ('Totales', 'etiqT1'), ('Totales', 'etRebs'), ('Totales', 'A'), ('Totales', 'BP'),
                    ('Totales', 'A-BP'), ('Totales', 'A-TCI'), ('Totales', 'BR'), ('Totales', 'TAP-F'),
                    ('Totales', 'TAP-C'), ]
    COLS_ULTP = [('UltimoPart', 'etFecha'), ('UltimoPart', 'Partido'), ('UltimoPart', 'resultado'),
                 ('UltimoPart', 'titular'), ('UltimoPart', 'etSegs'), ('UltimoPart', 'P'), ('UltimoPart', 'etiqT2'),
                 ('UltimoPart', 'etiqT3'), ('UltimoPart', 'etiqTC'), ('UltimoPart', 'ppTC'), ('UltimoPart', 'FP-F'),
                 ('UltimoPart', 'FP-C'), ('UltimoPart', 'etiqT1'), ('UltimoPart', 'etRebs'), ('UltimoPart', 'A'),
                 ('UltimoPart', 'BP'), ('UltimoPart', 'BR'), ('UltimoPart', 'TAP-F'), ('UltimoPart', 'TAP-C'), ]

    baseOPS = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (1, 0), (-1, -1), 'MIDDLE'),
               ('ALIGN', (1, 0), (-1, 0), 'CENTER'), ('FONT', (1, 0), (-1, 0), 'Helvetica-Bold'),
               ('ALIGN', (1, 1), (-1, -1), 'RIGHT'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
               ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (1, 0), (-1, -1), FONTSIZE + 1),
               ('LEFTPADDING', (1, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
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

    for claveTabla in ['totales', 'promedios', 'ultimo']:
        infoTabla = tablas[claveTabla]  # , [COLSIDENT +COLS_TOTALES], [COLSIDENT +COLS_ULTP]
        t = auxGeneraTablaJugs(auxDF, claveTabla, infoTabla, INFOTABLAJUGS, baseOPS, FORMATOCAMPOS, ANCHOLETRA,
                               repeatRows=1, abrev=abrev)

        result.append((infoTabla, t))

    return result


def tablaLiga(tempData: TemporadaACB, equiposAmarcar=None, currJornada: int = None):
    CELLPAD = 0.3 * mm
    FONTSIZE = 9

    datosAux, coordsJuPe, firstNegBal = datosTablaLiga(tempData, currJornada)

    alturas = [22] + [28.7] * (len(datosAux) - 2) + [21]
    anchos = [76] + [39] * (len(datosAux) - 2) + [38]

    listaEstilos = auxTablaLigaListaEstilos(CELLPAD, FONTSIZE, coordsJuPe, datosAux, equiposAmarcar, firstNegBal)
    tStyle = TableStyle(listaEstilos)

    t = Table(datosAux, style=tStyle, rowHeights=alturas, colWidths=anchos)

    return t


def auxTablaLigaListaEstilos(CELLPAD, FONTSIZE, coordsJuPe, datosAux, equiposAmarcar, firstNegBal):
    CANTGREYBAL = .70
    ANCHOMARCAPOS = 2
    colBal = colors.rgb2cmyk(CANTGREYBAL, CANTGREYBAL, CANTGREYBAL)

    listaEstilos = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (0, 0), (-1, -1), FONTSIZE),
                    ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
                    ('TOPPADDING', (0, 0), (-1, -1), CELLPAD), ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD),
                    ("BACKGROUND", (-1, 1), (-1, -2), colors.lightgrey),
                    ("BACKGROUND", (1, -1), (-2, -1), colors.lightgrey)]
    for i in range(1, len(datosAux) - 1):
        listaEstilos.append(("BACKGROUND", (i, i), (i, i), colBal))

    listNegBal = [(firstNegBal - 1, [colors.black, "squared", (2, 8)])] if firstNegBal else []

    for pos, resto in list(product(MARCADORESCLASIF, [[colors.black]])) + listNegBal:
        commH, commV, incr = ("LINEBELOW", "LINEAFTER", 0) if pos >= 0 else ("LINEABOVE", "LINEBEFORE", -1)
        posIni, posFin = (0, pos + incr) if pos >= 0 else (pos + incr, -1)

        listaEstilos.append([commH, (posIni, pos + incr), (posFin, pos + incr), ANCHOMARCAPOS] + resto)
        listaEstilos.append([commV, (pos + incr, posIni), (pos + incr, posFin), ANCHOMARCAPOS] + resto)

    # Etiquetas de equipos en descenso
    # Equipos para descenso (horizontal)
    listaEstilos.append(("LINEBEFORE", (-DESCENSOS - 1, 0), (-DESCENSOS - 1, 0), ANCHOMARCAPOS, colors.black))
    listaEstilos.append(("LINEBEFORE", (-1, 0), (-1, 0), ANCHOMARCAPOS, colors.black))
    listaEstilos.append(("LINEBELOW", (-DESCENSOS - 1, 0), (-2, 0), ANCHOMARCAPOS, colors.black))
    # Equipos para descenso (vertical)
    listaEstilos.append(("LINEAFTER", (0, -DESCENSOS - 1), (0, -2), ANCHOMARCAPOS, colors.black))
    listaEstilos.append(("LINEABOVE", (0, -DESCENSOS - 1), (0, -DESCENSOS - 1), ANCHOMARCAPOS, colors.black))
    listaEstilos.append(("LINEABOVE", (0, -1), (0, -1), ANCHOMARCAPOS, colors.black))

    # Marca los partidos del tipo (jugados o pendientes) que tenga menos
    claveJuPe = 'ju' if len(coordsJuPe['ju']) <= len(coordsJuPe['pe']) else 'pe'
    CANTGREYJUPE = .90
    colP = colors.rgb2cmyk(CANTGREYJUPE, CANTGREYJUPE, CANTGREYJUPE)
    for x, y in coordsJuPe[claveJuPe]:
        coord = (y + 1, x + 1)
        listaEstilos.append(("BACKGROUND", coord, coord, colP))

    if equiposAmarcar is not None:
        parEqs = set(listize(equiposAmarcar))
        seqIDs = [(pos, equipo.abrevsEq) for pos, equipo in enumerate(clasifLiga) if
                  equipo.abrevsEq.intersection(parEqs)]
        for pos, _ in seqIDs:
            listaEstilos.append(("BACKGROUND", (pos + 1, 0), (pos + 1, 0), colEq))
            listaEstilos.append(("BACKGROUND", (0, pos + 1), (0, pos + 1), colEq))
    return listaEstilos


def cabeceraPortada(tempData: TemporadaACB, datosSig: infoSigPartido):
    partido = datosSig.sigPartido
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = time2Str(partido['fechaPartido'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - "
        f"J: " f"<b>{j}</b><br/>{fh}</para>", style)

    cabLocal = datosCabEquipo(datosLocal, tempData, partido['fechaPartido'], currJornada=int(j))
    cabVisit = datosCabEquipo(datosVisit, tempData, partido['fechaPartido'], currJornada=int(j))

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def datosCabEquipo(datosEq, tempData, fecha, currJornada: int = None):
    recuperaClasifLiga(tempData, fecha)

    # TODO: Imagen (descargar imagen de escudo y plantarla)
    nombre = datosEq['nombcorto']

    clasifAux = equipo2clasif(clasifLiga, datosEq['abrev'])
    clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=currJornada)

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def recuperaEstadsGlobales(tempData):
    global estadGlobales
    global estadGlobalesOrden
    global allMagnsInEstads
    if estadGlobales is None:
        estadGlobales, estadGlobalesOrden = calculaEstadsYOrdenLiga(tempData, estadObj=ESTADISTICOEQ,
                                                                    catsAscending=CATESTADSEQASCENDING,
                                                                    cats2ignore=CATESTADSEQ2IGNORE)
        allMagnsInEstads = {magn for _, magn, _ in estadGlobales.columns}


def recuperaClasifLiga(tempData: TemporadaACB, fecha=None):
    global clasifLiga
    global numEqs
    global mitadEqs
    global tradEquipos

    if clasifLiga is None:
        clasifLiga = tempData.clasifLiga(fecha)
        numEqs = len(clasifLiga)
        mitadEqs = numEqs // 2

        for eq in clasifLiga:
            tradEquipos['a2n'][eq.abrevAusar] = eq.nombreCorto
            tradEquipos['n2a'][eq.nombreCorto] = eq.abrevAusar
            tradEquipos['i2a'][list(eq.idEq)[0]] = eq.abrevAusar


def datosRestoJornada(tempData: TemporadaACB, datosSig: infoSigPartido):
    """
    Devuelve la lista de partidos de la jornada a la que corresponde  el partidos siguiente del equipo objetivo
    :param tempData: datos descargados de ACB (ya cargados, no el fichero)
    :param datosSig: resultado de tempData.sigPartido (info sobre el siguiente partido del equipo objetivo
    :return: lista con información sobre partidos sacada del Calendario
    """
    result = list()
    sigPartido = datosSig.sigPartido
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


def tablaRestoJornada(tempData: TemporadaACB, datosSig: infoSigPartido):
    def infoEq(eqData: dict, jornada: int):
        abrev = eqData['abrev']

        clasifAux = equipo2clasif(clasifLiga, abrev)
        clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=jornada, addPendJornada=False)
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
            tFormato = "%a %d@%H:%M"
        result = tStamp.strftime(tFormato)
        return result

    def preparaDatos(datos, tstampRef):
        intData = list()
        for p in sorted(datos, key=itemgetter('fechaPartido')):
            info = {'pendiente': p['pendiente'], 'fecha': etFecha(p['fechaPartido'], tstampRef)}
            for loc in LocalVisitante:
                info[loc] = infoEq(p['equipos'][loc], jornada=jornada)
            if not p['pendiente']:
                info['resultado'] = infoRes(p)

            intData.append(info)
        return intData

    # Data preparation
    sigPartido = datosSig.sigPartido
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

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                         ('LEADING', (0, 0), (-1, -1), 0), ("SPAN", (0, 0), (-1, 0))])

    ANCHOEQUIPO = 128
    ANCHOCENTRO = 75
    t = Table(data=filas, style=tStyle, colWidths=[ANCHOEQUIPO, ANCHOCENTRO, ANCHOEQUIPO], rowHeights=FONTSIZE + 4)

    return t


def datosTablaClasif(tempData: TemporadaACB, datosSig: infoSigPartido) -> list[filaTablaClasif]:
    # Data preparation
    sigPartido = datosSig.sigPartido
    abrsEqs = sigPartido['participantes']
    jornada = int(sigPartido['jornada'])
    muestraJornada = len(tempData.Calendario.Jornadas[jornada]['partidos']) > 0
    recuperaClasifLiga(tempData)

    result = list()
    for posic, eq in enumerate(clasifLiga):
        nombEqAux = eq.nombreCorto
        notaClas = auxCalculaBalanceStrSuf(record=eq, addPendientes=True, currJornada=jornada,
                                           addPendJornada=muestraJornada)
        nombEq = f"{nombEqAux}{notaClas}"
        victs = eq.V
        derrs = eq.D
        jugs = victs + derrs
        ratio = (100.0 * victs / jugs) if (jugs != 0) else 0.0
        puntF = eq.Pfav
        puntC = eq.Pcon
        diffP = puntF - puntC
        resaltaFila = bool(abrsEqs.intersection(eq.abrevsEq))

        fila = filaTablaClasif(posic=posic + 1, nombre=nombEq, jugs=jugs, victs=victs, derrs=derrs, ratio=ratio,
                               puntF=puntF, puntC=puntC, diffP=diffP, resalta=resaltaFila)

        result.append(fila)

    return result


def tablaClasifLiga(tempData: TemporadaACB, datosSig: infoSigPartido):
    FONTPARA = 8.5
    FONTSIZE = 8

    def preparaFila(dato):
        result = [Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.posic}</para>"),
                  Paragraph(f"<para align='left' fontsize={FONTPARA}>{dato.nombre}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.jugs}</para>"),
                  Paragraph(f"<para align='center' fontsize={FONTPARA}>{dato.victs:2}-{dato.derrs:2}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.ratio:3.0f}%</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.puntF:4}/{dato.puntC:4}</para>"),
                  Paragraph(f"<para align='right' fontsize={FONTPARA}>{dato.diffP}</para>")]
        return result

    recuperaClasifLiga(tempData)
    filasClasLiga = datosTablaClasif(tempData, datosSig)
    posFirstNegBal = auxCalculaFirstBalNeg(clasifLiga)
    filasAresaltar = list()
    filaCab = [Paragraph("<para align='center'><b>#</b></para>"),
               Paragraph("<para align='center'><b>Equipo</b></para>"),
               Paragraph("<para align='center'><b>J</b></para>"), Paragraph("<para align='center'><b>V-D</b></para>"),
               Paragraph("<para align='center'><b>%</b></para>"),
               Paragraph("<para align='center'><b>PF / PC </b></para>"),
               Paragraph("<para align='center'><b>Df</b></para>")]

    lStyle = [('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE * 0.8),
              ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
              ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1)]

    listasClas = [[filaCab], [filaCab]]
    listasStyles = [TableStyle(lStyle), TableStyle(lStyle)]

    # Crea las listas para las subtablas
    for posic, datosFila in enumerate(filasClasLiga):
        t, e = posic // mitadEqs, posic % mitadEqs

        listasClas[t].append(preparaFila(datosFila))
        if datosFila.resalta:
            filasAresaltar.append((t, e))

    ANCHOMARCAPOS = 2
    for pos in MARCADORESCLASIF:
        commH = "LINEBELOW"
        incr = 0 if pos >= 0 else -1
        t = 0 if pos >= 0 else 1
        listasStyles[t].add(commH, (0, pos + incr), (-1, pos + incr), ANCHOMARCAPOS, colors.black)

    # Balance negativo
    if posFirstNegBal is not None:
        t, e = posFirstNegBal // mitadEqs, posFirstNegBal % mitadEqs
        listasStyles[t].add("LINEABOVE", (0, e), (-1, e), ANCHOMARCAPOS, colors.black, "squared", (1, 8))

    # Marca equipos del programa
    if filasAresaltar:
        for t, e in filasAresaltar:
            listasStyles[t].add("BACKGROUND", (0, e + 1), (-1, e + 1), colEq)

    ANCHOPOS = 21.5
    ANCHOEQUIPO = 92
    ANCHOPARTS = 23.7
    ANCHOPERC = 30
    ANCHOPUNTS = 54.5
    ANCHODIFF = 29.5
    listaAnchos = [ANCHOPOS, ANCHOEQUIPO, ANCHOPARTS, ANCHOPARTS * 1.4, ANCHOPERC, ANCHOPUNTS, ANCHODIFF]

    listaTablas = [Table(data=listasClas[t], style=listasStyles[t], colWidths=listaAnchos, rowHeights=FONTSIZE + 4) for
                   t in range(2)]

    result = Table(data=[listaTablas])
    return result


def calculaMaxMinMagn(ser: pd.Series, ser_orden: pd.Series):
    def getValYEtq(serie, serie_orden, targ_orden):
        auxSerTargOrden: pd.Series = serie_orden == targ_orden
        numOrdenTarg = auxSerTargOrden.sum()
        abrevs = set(auxSerTargOrden[auxSerTargOrden].index)
        etiqTarg = f"x{numOrdenTarg}" if numOrdenTarg > 1 else serie_orden[serie_orden == targ_orden].index[0]
        valTarg = serie[serie_orden == targ_orden].iloc[0]
        return valTarg, etiqTarg, abrevs

    # Mejor cuanto el orden sea menor: 1 mejor > 18 peor
    maxVal, maxEtq, maxAbrevs = getValYEtq(ser, ser_orden, ser_orden.min())
    minVal, minEtq, minAbrevs = getValYEtq(ser, ser_orden, ser_orden.max())

    return tuplaMaxMinMagn(minVal=minVal, minEtq=minEtq, minAbrevs=minAbrevs, maxVal=maxVal, maxEtq=maxEtq,
                           maxAbrevs=maxAbrevs, abrevs2add=maxAbrevs.union(minAbrevs))


def datosAnalisisEstadisticos(tempData: TemporadaACB, datosSig: infoSigPartido, magn2include: list, magnsAscending=None,
                              infoCampos: dict = REPORTLEYENDAS
                              ):
    catsAscending = magnsAscending if magnsAscending else set()
    auxEtiqLeyenda = infoCampos if infoCampos else dict()

    recuperaEstadsGlobales(tempData)

    targetAbrevs = auxFindTargetAbrevs(tempData, datosSig)

    result = dict()

    estadsInexistentes = set()
    abrevs2leyenda = set()
    clavesEnEstads = set(sorted(estadGlobales.columns))

    for claveEst in magn2include:

        kEq, kMagn = claveEst

        if kMagn not in auxEtiqLeyenda:
            print(f"tablaAnalisisEstadisticos.filasTabla: magnitud '{kMagn}' no está en descripciones.Usando {kMagn} "
                  f"para etiqueta")
        descrMagn = auxEtiqLeyenda.get(kMagn, dict())

        etiq = descrMagn.get('etiq', kMagn)
        formatoMagn = descrMagn.get('formato', DEFAULTNUMFORMAT)
        leyendaMagn = descrMagn.get('leyenda', None)

        clave2use = (kEq, kMagn, ESTADISTICOEQ)
        if clave2use not in clavesEnEstads:
            estadsInexistentes.add(clave2use)
            continue

        esCreciente = esEstCreciente(kMagn, catsAscending, kEq)
        labCreciente = "C" if esCreciente else "D"

        serMagn: pd.Series = estadGlobales[clave2use]
        serMagnOrden: pd.Series = estadGlobalesOrden[clave2use]
        magnMed = serMagn.mean()
        magnStd = serMagn.std()

        datosEqs = {k: serMagn[targetAbrevs[k]] for k in LocalVisitante}
        datosEqsOrd = {k: int(serMagnOrden[targetAbrevs[k]]) for k in LocalVisitante}

        infoMaxMinMagn = calculaMaxMinMagn(serMagn, serMagnOrden)
        abrevs2leyenda = abrevs2leyenda.union(infoMaxMinMagn.abrevs2add)

        resaltaLocal = datosEqsOrd['Local'] < datosEqsOrd['Visitante']
        resaltaVisit = datosEqsOrd['Visitante'] < datosEqsOrd['Local']

        resaltaMax = min(serMagnOrden) in set(datosEqsOrd.values())
        resaltaMin = max(serMagnOrden) in set(datosEqsOrd.values())

        newRecord = filaComparEstadistica(magn=kMagn, nombreMagn=etiq, isAscending=labCreciente,
                                          locAbr=targetAbrevs['Local'], locMagn=datosEqs['Local'], locHigh=resaltaLocal,
                                          locRank=datosEqsOrd['Local'], maxMagn=infoMaxMinMagn.maxVal,
                                          maxAbr=infoMaxMinMagn.maxEtq, maxHigh=resaltaMax, ligaMed=magnMed,
                                          ligaStd=magnStd, minMagn=infoMaxMinMagn.minVal, minAbr=infoMaxMinMagn.minEtq,
                                          minHigh=resaltaMin, visAbr=targetAbrevs['Visitante'],
                                          visMagn=datosEqs['Visitante'], visRank=datosEqsOrd['Visitante'],
                                          visHigh=resaltaVisit, formatoMagn=formatoMagn, leyenda=leyendaMagn)

        result[claveEst] = newRecord

    if estadsInexistentes:
        raise ValueError(
            f"datosAnalisisEstadisticos: los siguientes valores no existen: {estadsInexistentes}. " + f"Parametro: "
                                                                                                      f"{magn2include}. "
                                                                                                      f"Columnas "
                                                                                                      f"posibles: "
                                                                                                      f"{
                                                                                                      clavesEnEstads}")
    return result, abrevs2leyenda


def tablaAnalisisEstadisticos(tempData: TemporadaACB, datosSig: infoSigPartido, magns2incl: list | set | None = None,
                              magnsCrecientes: list | set | None = None
                              ) -> Table:
    catsAscending = {} if magnsCrecientes is None else set(magnsCrecientes)

    recuperaEstadsGlobales(tempData)
    targetAbrevs = auxFindTargetAbrevs(tempData, datosSig)

    clavesEq, clavesRiv = allMagnsInEstads, allMagnsInEstads
    if isinstance(magns2incl, list):
        clavesEq = list(magns2incl)
        clavesRiv = clavesEq
    elif isinstance(magns2incl, dict):
        clavesEq = magns2incl.get('Eq', {})
        clavesRiv = magns2incl.get('Rival', {})
    claves2wrk = list(product(['Eq'], clavesEq)) + list(product(['Rival'], clavesRiv))
    if len(claves2wrk) == 0:
        raise ValueError(f"tablaAnalisisEstadisticos: No hay valores para incluir en la tabla: parametro {magns2incl}")

    datos, abrevs2leyenda = datosAnalisisEstadisticos(tempData, datosSig, magnsAscending=catsAscending,
                                                      magn2include=claves2wrk)

    FONTSIZE = 8

    headerStyle = ParagraphStyle('tabEstadsHeader', fontSize=FONTSIZE + 2, alignment=TA_CENTER, leading=12)
    rowHeaderStyle = ParagraphStyle('tabEstadsRowHeader', fontSize=FONTSIZE, alignment=TA_LEFT, leading=10)
    cellStyle = ParagraphStyle('tabEstadsCell', fontSize=FONTSIZE, alignment=TA_RIGHT, leading=10)

    ANCHOEQL = 14.2
    ANCHOLABEL = 68.4
    ANCHOEQUIPO = 55.5
    ANCHOMAXMIN = 68.9
    ANCHOLIGA = 65.2
    ANCHOLEYENDA = 170

    LISTAANCHOS = [ANCHOEQL, ANCHOLABEL, ANCHOEQUIPO, ANCHOEQUIPO, ANCHOMAXMIN, ANCHOLIGA, ANCHOMAXMIN]

    filaCab = [None, Paragraph(auxBold("Estad"), style=headerStyle),
               Paragraph(auxBold(f"{targetAbrevs['Local']}"), style=headerStyle),
               Paragraph(auxBold(f"{targetAbrevs['Visitante']}"), style=headerStyle),
               Paragraph(auxBold("Mejor"), style=headerStyle), Paragraph(auxBold("ACB"), style=headerStyle),
               Paragraph(auxBold("Peor"), style=headerStyle)]

    filasTabla, leyendas = auxFilasTablaEstadisticos(datos, clavesEquipo=clavesEq, clavesRival=clavesRiv,
                                                     estiloCabCelda=rowHeaderStyle, estiloCelda=cellStyle)

    EXTRALEYENDA = 0
    ESTILOLEYENDA = []
    if leyendas:
        LISTAANCHOS.append(ANCHOLEYENDA)
        filaCab.append(Paragraph(auxBold("Leyenda"), style=headerStyle))
        EXTRALEYENDA = -1
        ESTILOLEYENDA = [('SPAN', (-1, 1), (-1, -1)), ('VALIGN', (-1, 1), (-1, -1), 'TOP')]

        filasTabla[0][-1] = auxGeneraLeyendaEstadsCelda(leyendas, FONTSIZE,
                                                        abrevs2leyenda.union(set(targetAbrevs.values())))

    listaEstilos = [('BOX', (1, 1), (-1 + EXTRALEYENDA, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (1, 1), (-1 + EXTRALEYENDA, -1), 0.5, colors.black), ('SPAN', (0, 1), (0, len(clavesEq))),
                    ('SPAN', (0, len(clavesEq)), (0, -1)),
                    ('BOX', (1, 1), (-1 + EXTRALEYENDA, len(clavesEq)), 2, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('BOX', (1, -len(clavesRiv)), (-1 + EXTRALEYENDA, -1), 2, colors.black), ] + ESTILOLEYENDA

    listaFilas = [filaCab] + filasTabla

    tStyle = TableStyle(listaEstilos)

    tabla1 = Table(data=listaFilas, style=tStyle, colWidths=LISTAANCHOS, rowHeights=11.2)

    return tabla1


def tablaEstadsBasicas(tempData: TemporadaACB, datosSig: infoSigPartido):
    sigPartido = datosSig.sigPartido

    datos = {loc: datosEstadsBasicas(tempData, sigPartido['equipos'][loc]) for loc in LocalVisitante}

    style = ParagraphStyle('Normal', align='left', fontName='Helvetica', fontSize=9, leading=9.8, )

    datosTabla = [[Paragraph(datos[loc], style)] for loc in LocalVisitante]
    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('LEADING', (0, 0), (-1, -1), 0)])

    t = Table(data=datosTabla, colWidths=[77 * mm], rowHeights=20.5 * mm, style=tStyle)

    return t


def bloqueRestoJYBasics(tempData: TemporadaACB, datosSig: infoSigPartido):
    tabEBasics = tablaEstadsBasicas(tempData, datosSig)
    tabRestoJ = tablaRestoJornada(tempData, datosSig)

    tStyle = TableStyle(
        [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEADING', (0, 0), (-1, -1), 0), ('LEFTPADDING', (0, 0), (-1, -1), 3),
         ('RIGHTPADDING', (0, 0), (-1, -1), 3),

         ])

    datosTabla = [[tabRestoJ, tabEBasics]]
    anchoCols = [118 * mm, 77 * mm]

    t = Table(data=datosTabla, colWidths=anchoCols, style=tStyle)

    return t


def metadataPrograma(tempData: TemporadaACB):
    FONTSIZE = 6

    FORMATOfecha = "%Y-%m-%d %H:%M (%z)"
    fechaGen = strftime(FORMATOfecha, gmtime())
    tempDesc = strftime(FORMATOfecha, tempData.timestamp)
    mensaje = (f"Datos procedentes de https://www.acb.com y elaboración propia. Generado en {fechaGen}. Datos "
               f"descargados en {tempDesc}")

    metadataStyle = ParagraphStyle('tabEstadsRowHeader', fontSize=FONTSIZE, alignment=TA_LEFT, leading=1)

    result = Paragraph(mensaje, style=metadataStyle)

    return result

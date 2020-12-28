from collections import defaultdict
from copy import copy

import pandas as pd
import reportlab.lib.colors as colors
import sys
from configargparse import ArgumentParser
from math import isnan
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Table, SimpleDocTemplate, Paragraph, TableStyle, Spacer, NextPageTemplate, PageTemplate, \
    Frame, PageBreak
from time import strftime, struct_time

from SMACB.CalendarioACB import NEVER
from SMACB.FichaJugador import TRADPOSICION
from SMACB.PartidoACB import LocalVisitante, OtherTeam
from SMACB.TemporadaACB import TemporadaACB, extraeCampoYorden
from Utils.FechaHora import Time2Str

estadGlobales = None
ESTAD_MEDIA = 0
ESTAD_MEDIANA = 1
ESTAD_DEVSTD = 2
ESTAD_MAX = 3
ESTAD_MIN = 4
ESTAD_COUNT = 5
ESTAD_SUMA = 6

ESTADISTICOEQ = ESTAD_MEDIA
ESTADISTICOJUG = ESTAD_MEDIA

COLS_IDENTIFIC_JUG = ['competicion', 'temporada', 'CODequipo', 'IDequipo', 'codigo', 'dorsal', 'nombre']

LOCALNAMES = {'Local', 'L', 'local'}
VISITNAME = {'Visitante', 'V', 'visitante'}


def GENERADORETTIRO(*kargs, **kwargs):
    return lambda f: auxEtiqTiros(f, *kargs, **kwargs)


def GENERADORETREBOTE(*kargs, **kwargs):
    return lambda f: auxEtiqRebotes(f, *kargs, **kwargs)


def GENERADORFECHA(*kargs, **kwargs):
    return lambda f: auxEtFecha(f, *kargs, **kwargs)


def GENERADORTIEMPO(*kargs, **kwargs):
    return lambda f: auxEtiqTiempo(f, *kargs, **kwargs)


FORMATOCAMPOS = {'entero': {'numero': '{:3.0f}'}, 'float': {'numero': '{:4.2f}'}, }

INFOTABLAJUGS = {
    ('Jugador', 'dorsal'): {'etiq': 'D', 'ancho': 3},
    ('Jugador', 'nombre'): {'etiq': 'Nombre', 'ancho': 22, 'alignment': 'LEFT'},
    ('Trayectoria', 'Acta'): {'etiq': 'Cv', 'ancho': 3},
    ('Trayectoria', 'Jugados'): {'etiq': 'Ju', 'ancho': 3},
    ('Trayectoria', 'Titular'): {'etiq': 'Tt', 'ancho': 3},
    ('Trayectoria', 'Vict'): {'etiq': 'Vc', 'ancho': 3},

    ('Promedios', 'etSegs'): {'etiq': 'Min', 'ancho': 7, 'generador': GENERADORTIEMPO(col='Segs')},
    ('Promedios', 'P'): {'etiq': 'P', 'ancho': 7, 'formato': 'float'},
    ('Promedios', 'etiqT2'): {'etiq': 'T2', 'ancho': 19, 'generador': GENERADORETTIRO('2', entero=False)},
    ('Promedios', 'etiqT3'): {'etiq': 'T3', 'ancho': 19, 'generador': GENERADORETTIRO(tiro='3', entero=False)},
    ('Promedios', 'etiqTC'): {'etiq': 'TC', 'ancho': 19, 'generador': GENERADORETTIRO('C', False)},
    ('Promedios', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'etiqT1'): {'etiq': 'TL', 'ancho': 19, 'generador': GENERADORETTIRO('1', False)},
    ('Promedios', 'etRebs'): {'etiq': 'Rebs', 'ancho': 18, 'generador': GENERADORETREBOTE(entero=False)},
    ('Promedios', 'A'): {'etiq': 'A', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'BP'): {'etiq': 'BP', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'BR'): {'etiq': 'BR', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'TAP-F'): {'etiq': 'Tap', 'ancho': 6, 'formato': 'float'},
    ('Promedios', 'TAP-C'): {'etiq': 'Tp R', 'ancho': 6, 'formato': 'float'},

    ('Totales', 'etSegs'): {'etiq': 'Min', 'ancho': 8, 'generador': GENERADORTIEMPO(col='Segs')},
    ('Totales', 'P'): {'etiq': 'P', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'etiqT2'): {'etiq': 'T2', 'ancho': 19, 'generador': GENERADORETTIRO('2', entero=True)},
    ('Totales', 'etiqT3'): {'etiq': 'T3', 'ancho': 19, 'generador': GENERADORETTIRO('3', entero=True)},
    ('Totales', 'etiqTC'): {'etiq': 'TC', 'ancho': 19, 'generador': GENERADORETTIRO('C', entero=True)},
    ('Totales', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
    ('Totales', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'etiqT1'): {'etiq': 'TL', 'ancho': 19, 'generador': GENERADORETTIRO('1', entero=True)},
    ('Totales', 'etRebs'): {'etiq': 'Rebs', 'ancho': 18, 'generador': GENERADORETREBOTE(entero=True)},
    ('Totales', 'A'): {'etiq': 'A', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'BP'): {'etiq': 'BP', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'BR'): {'etiq': 'BR', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'TAP-F'): {'etiq': 'Tap', 'ancho': 6, 'formato': 'entero'},
    ('Totales', 'TAP-C'): {'etiq': 'Tp R', 'ancho': 6, 'formato': 'entero'},

    ('UltimoPart', 'etFecha'): {'etiq': 'Fecha', 'ancho': 6, 'generador': GENERADORFECHA(col='Fecha'),
                                'alignment': 'CENTER'},
    ('UltimoPart', 'Partido'): {'etiq': 'Rival', 'ancho': 22, 'alignment': 'LEFT'},
    ('UltimoPart', 'resultado'): {'etiq': 'Vc', 'ancho': 5, 'alignment': 'CENTER'},
    ('UltimoPart', 'titular'): {'etiq': 'Tt', 'ancho': 5, 'alignment': 'CENTER'},
    ('UltimoPart', 'etSegs'): {'etiq': 'Min', 'ancho': 8, 'generador': GENERADORTIEMPO(col='Segs')},
    ('UltimoPart', 'P'): {'etiq': 'P', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'etiqT2'): {'etiq': 'T2', 'ancho': 15, 'generador': GENERADORETTIRO('2', entero=True)},
    ('UltimoPart', 'etiqT3'): {'etiq': 'T3', 'ancho': 15, 'generador': GENERADORETTIRO('3', entero=True)},
    ('UltimoPart', 'etiqTC'): {'etiq': 'TC', 'ancho': 15, 'generador': GENERADORETTIRO('C', entero=True)},
    ('UltimoPart', 'ppTC'): {'etiq': 'P/TC', 'ancho': 6, 'formato': 'float'},
    ('UltimoPart', 'FP-F'): {'etiq': 'F com', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'FP-C'): {'etiq': 'F rec', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'etiqT1'): {'etiq': 'TL', 'ancho': 15, 'generador': GENERADORETTIRO('1', entero=True)},
    ('UltimoPart', 'etRebs'): {'etiq': 'Rebs', 'ancho': 14, 'generador': GENERADORETREBOTE(entero=True)},
    ('UltimoPart', 'A'): {'etiq': 'A', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'BP'): {'etiq': 'BP', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'BR'): {'etiq': 'BR', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'TAP-C'): {'etiq': 'Tap', 'ancho': 6, 'formato': 'entero'},
    ('UltimoPart', 'TAP-F'): {'etiq': 'Tp R', 'ancho': 6, 'formato': 'entero'},
}

ESTILOS = getSampleStyleSheet()


def auxCalculaBalanceStr(record):
    victorias = record.get('V', 0)
    derrotas = record.get('D', 0)
    texto = f"{victorias}-{derrotas}"

    return texto


def auxEtiqPartido(tempData: TemporadaACB, rivalAbr, esLocal=None, locEq=None, usaAbr=False, usaLargo=False):
    if (esLocal is None) and (locEq is None):
        raise ValueError("auxEtiqPartido: debe aportar o esLocal o locEq")

    auxLoc = esLocal if (esLocal is not None) else (locEq in LOCALNAMES)
    prefLoc = "vs " if auxLoc else "@"

    ordenNombre = -1 if usaLargo else 0

    nombre = rivalAbr if usaAbr else sorted(tempData.Calendario.tradEquipos['c2n'][rivalAbr], key=lambda n: len(n))[
        ordenNombre]

    result = f"{prefLoc}{nombre}"

    return result


def auxEtiqRebotes(df, entero: bool = True) -> str:
    if isnan(df['R-D']):
        return "-"

    formato = "{:3}+{:3} {:3}" if entero else "{:6.2f}+{:6.2f} {:6.2f}"

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
    formato = "{:3}/{:3} {:6.2f}%" if entero else "{:6.2f}/{:6.2f} {:6.2f}%"

    etTC = f"T{tiro}-C"
    etTI = f"T{tiro}-I"
    etTpc = f"T{tiro}%"

    if df[etTI] == 0.0 or isnan(df[etTI]):
        return "-"

    valores = [int(v) if entero else v for v in [df[etTC], df[etTI]]] + [df[etTpc]]

    result = formato.format(*valores)

    return result


def auxEtFecha(f, col, formato="%d-%m"):
    if f is None:
        return "-"

    dato = f[col]
    result = dato.strftime(formato)

    return result


def auxGeneraTabla(dfDatos, collist, colSpecs, estiloTablaBaseOps, formatos=None, charWidth=10):
    dfColList = []
    filaCab = []
    anchoCols = []
    tStyle = TableStyle(estiloTablaBaseOps)

    if formatos is None:
        formatos = dict()

    for i, colkey in enumerate(collist):
        level, etiq = colkey
        colSpec = colSpecs.get(colkey, {})
        newCol = dfDatos[level].apply(colSpec['generador'], axis=1) if 'generador' in colSpec else dfDatos[[colkey]]

        if 'formato' in colSpec:
            etiqFormato = colSpec['formato']
            if colSpec['formato'] not in formatos:
                raise KeyError(
                    f"auxGeneraTabla: columna '{colkey}': formato '{etiqFormato}' desconocido. Formatos conocidos: {formatos}")
            formatSpec = formatos[etiqFormato]

            if 'numero' in formatSpec:
                newCol = newCol.apply(lambda c: c.map(formatSpec['numero'].format))

        newEtiq = colSpec.get('etiq', etiq)
        newAncho = colSpec.get('ancho', 10) * charWidth

        dfColList.append(newCol)
        filaCab.append(newEtiq)
        anchoCols.append(newAncho)
        if 'alignment' in colSpec:
            newCmdStyle = ["ALIGN", (i, 1), (i, -1), colSpec['alignment']]
            tStyle.add(*newCmdStyle)

    datosAux = pd.concat(dfColList, axis=1, join='outer', names=filaCab)

    datosTabla = [filaCab] + datosAux.to_records(index=False, column_dtypes='object').tolist()

    t = Table(datosTabla, style=tStyle, colWidths=anchoCols)

    return t


def cabeceraPortada(partido, tempData):
    datosLocal = partido['equipos']['Local']
    datosVisit = partido['equipos']['Visitante']
    compo = partido['cod_competicion']
    edicion = partido['cod_edicion']
    j = partido['jornada']
    fh = Time2Str(partido['fecha'])

    style = ParagraphStyle('cabStyle', align='center', fontName='Helvetica', fontSize=20, leading=22, )

    cadenaCentral = Paragraph(
        f"<para align='center' fontName='Helvetica' fontSize=20 leading=22><b>{compo}</b> {edicion} - J: <b>{j}</b><br/>{fh}</para>",
        style)

    cabLocal = datosCabEquipo(datosLocal, tempData, partido['fecha'])
    cabVisit = datosCabEquipo(datosVisit, tempData, partido['fecha'])

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])
    t = Table(data=[[cabLocal, cadenaCentral, cabVisit]], colWidths=[60 * mm, 80 * mm, 60 * mm], style=tStyle)  #

    return t


def cargaTemporada(fname):
    result = TemporadaACB()
    result.cargaTemporada(fname)

    return result


def datosCabEquipo(datosEq, tempData, fecha):
    # TODO: Imagen
    nombre = datosEq['nombcorto']

    clasifAux = tempData.clasifEquipo(datosEq['abrev'], fecha)
    clasifStr = auxCalculaBalanceStr(clasifAux)

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def datosEstadsEquipoPortada(tempData: TemporadaACB, eq: str):
    global estadGlobales
    if estadGlobales is None:
        estadGlobales = tempData.estadsLiga()

    targAbrev = list(tempData.Calendario.abrevsEquipo(eq).intersection(estadGlobales.keys()))[0]

    pFav, pFavOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'P', ESTADISTICOEQ)
    pCon, pConOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'Priv', ESTADISTICOEQ, False)

    pos, posOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'POS', ESTADISTICOEQ)
    OER, OEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OER', ESTADISTICOEQ)
    OERpot, OERpotOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'OERpot', ESTADISTICOEQ)
    DER, DEROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'OER', ESTADISTICOEQ, False)

    T2C, T2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-C', ESTADISTICOEQ)
    T2I, T2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2-I', ESTADISTICOEQ)
    T2pc, T2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T2%', ESTADISTICOEQ)
    T3C, T3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-C', ESTADISTICOEQ)
    T3I, T3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3-I', ESTADISTICOEQ)
    T3pc, T3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T3%', ESTADISTICOEQ)
    TCC, TCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-C', ESTADISTICOEQ)
    TCI, TCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC-I', ESTADISTICOEQ)
    TCpc, TCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'TC%', ESTADISTICOEQ)
    ppTC, ppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'ppTC', ESTADISTICOEQ)
    ratT3, ratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 't3/tc-I', ESTADISTICOEQ)
    Fcom, FcomOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'FP-F', ESTADISTICOEQ, False)
    Frec, FrecOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'FP-F', ESTADISTICOEQ, True)
    T1C, T1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-C', ESTADISTICOEQ)
    T1I, T1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1-I', ESTADISTICOEQ)
    T1pc, T1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'T1%', ESTADISTICOEQ)

    RebD, RebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-D', ESTADISTICOEQ, True)
    RebO, RebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'R-O', ESTADISTICOEQ, True)
    RebT, RebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'REB-T', ESTADISTICOEQ, True)
    EffRebD, EffRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebD', ESTADISTICOEQ, True)
    EffRebO, EffRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'EffRebO', ESTADISTICOEQ, True)

    A, AOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A', ESTADISTICOEQ, True)
    BP, BPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BP', ESTADISTICOEQ, False)
    BR, BROrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'BR', ESTADISTICOEQ, True)
    ApBP, ApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/BP', ESTADISTICOEQ, True)
    ApTCC, ApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'eq', 'A/TC-C', ESTADISTICOEQ, True)

    ### Valores del equipo rival

    rT2C, rT2COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-C', ESTADISTICOEQ)
    rT2I, rT2IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2-I', ESTADISTICOEQ)
    rT2pc, rT2pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T2%', ESTADISTICOEQ)
    rT3C, rT3COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-C', ESTADISTICOEQ)
    rT3I, rT3IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3-I', ESTADISTICOEQ)
    rT3pc, rT3pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T3%', ESTADISTICOEQ)
    rTCC, rTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-C', ESTADISTICOEQ)
    rTCI, rTCIOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC-I', ESTADISTICOEQ)
    rTCpc, rTCpcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'TC%', ESTADISTICOEQ)
    rppTC, rppTCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'ppTC', ESTADISTICOEQ)
    rratT3, rratT3Ord = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 't3/tc-I', ESTADISTICOEQ)
    rT1C, rT1COrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-C', ESTADISTICOEQ)
    rT1I, rT1IOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1-I', ESTADISTICOEQ)
    rT1pc, rT1pcOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'T1%', ESTADISTICOEQ)

    rRebD, rRebDOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-D', ESTADISTICOEQ, True)
    rRebO, rRebOOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'R-O', ESTADISTICOEQ, True)
    rRebT, rRebTOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'REB-T', ESTADISTICOEQ, True)

    rA, rAOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A', ESTADISTICOEQ, True)
    rBP, rBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BP', ESTADISTICOEQ, False)
    rBR, rBROrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'BR', ESTADISTICOEQ, True)
    rApBP, rApBPOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/BP', ESTADISTICOEQ, True)
    rApTCC, rApTCCOrd = extraeCampoYorden(estadGlobales, targAbrev, 'rival', 'A/TC-C', ESTADISTICOEQ, True)

    ###

    resultEq = f"""
<b>PF</b>: {pFav:.2f}({pFavOrd}) <b>/</b> <b>PC</b>: {pCon:.2f}({pConOrd}) <b>/</b> 
<b>Pos</b>: {pos:.2f}({posOrd}) <b>/</b> <b>OER</b>: {OER:.2f}({OEROrd}) <b>/</b> <b>DER</b>: {DER:.2f}({DEROrd}) <b>/</b>
<b>T2</b>: {T2C:.2f}({T2IOrd})/{T2I:.2f}({T2IOrd}) {T2pc:.2f}%({T2pcOrd}) <b>/</b> <b>T3</b>: {T3C:.2f}({T3IOrd})/{T3I:.2f}({T3IOrd}) {T3pc:.2f}%({T3pcOrd}) <b>/</b>
<b>TC</b>: {TCC:.2f}({TCIOrd})/{TCI:.2f}({TCIOrd}) {TCpc:.2f}%({TCpcOrd}) <b>/</b> <b>P por TC-I</b>: {ppTC:.2f}({ppTCOrd}) T3-I/TC-I {ratT3:.2f}%({ratT3Ord}) <b>/</b>
<b>F com</b>: {Fcom:.2f}({FcomOrd})  <b>/</b> <b>F rec</b>: {Frec:.2f}({FrecOrd})  <b>/</b> <b>TL</b>: {T1C:.2f}({T1COrd})/{T1I:.2f}({T1IOrd}) {T1pc:.2f}%({T1pcOrd}) <b>/</b>
<b>Reb</b>: {RebD:.2f}({RebDOrd})+{RebO:.2f}({RebOOrd}) {RebT:.2f}({RebTOrd}) <b>/</b> <b>Eff D</b>: {EffRebD:.2f}({EffRebDOrd}) <b>Eff O</b>: {EffRebO:.2f}({EffRebOOrd}) <b>/</b>
<b>A</b>: {A:.2f}({AOrd}) <b>/</b> <b>BP</b>: {BP:.2f}({BPOrd}) <b>/</b> <b>BR</b>: {BR:.2f}({BROrd}) <b>/</b> <b>A/BP</b>: {ApBP:.2f}({ApBPOrd}) <b>/</b> <b>A/Can</b>: {ApTCC:.2f}({ApTCCOrd})<br/>

<B>RIVAL</B><br/>
<b>T2</b>: {rT2C:.2f}({rT2IOrd})/{rT2I:.2f}({rT2IOrd}) {rT2pc:.2f}%({rT2pcOrd}) <b>/</b> <b>T3</b>: {rT3C:.2f}({rT3IOrd})/{rT3I:.2f}({rT3IOrd}) {rT3pc:.2f}%({rT3pcOrd}) <b>/</b>
<b>TC</b>: {rTCC:.2f}({rTCIOrd})/{rTCI:.2f}({rTCIOrd}) {rTCpc:.2f}%({rTCpcOrd}) <b>/</b> <b>P por TC-I</b>: {rppTC:.2f}({rppTCOrd}) T3-I/TC-I  {rratT3:.2f}%({rratT3Ord}) <b>/</b>
<b>TL</b>: {rT1C:.2f}({rT1COrd})/{rT1I:.2f}({rT1IOrd}) {rT1pc:.2f}%({rT1pcOrd}) <b>/</b> <b>Reb</b>: {rRebD:.2f}({rRebDOrd})+{rRebO:.2f}({rRebOOrd}) {rRebT:.2f}({rRebTOrd}) <b>/</b>
<b>A</b>: {rA:.2f}({rAOrd}) <b>/</b> <b>BP</b>: {rBP:.2f}({rBPOrd}) <b>/</b> <b>BR</b>: {rBR:.2f}({rBROrd}) <b>/</b> <b>A/BP</b>: {rApBP:.2f}({rApBPOrd}) <b>/</b> <b>A/Can</b>: {rApTCC:.2f}({rApTCCOrd})
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


def calcEstadAdicionalesTC(df: pd.DataFrame) -> pd.DataFrame:
    # Genera tiros de Campo
    df['TC-I'] = df['T2-I'] + df['T3-I']
    df['TC-C'] = df['T2-C'] + df['T3-C']
    # Recalcula porcentajes
    for t in '123C':
        df[f'T{t}%'] = df[f'T{t}-C'] / df[f'T{t}-I'] * 100.0
    # Eficiencia de los tiros
    df['PTC'] = (2 * df['T2-C'] + 3 * df['T3-C'])
    df['ppTC'] = df['PTC'] / df['TC-I']

    return df


def calcEstadisticasJugador(df, campoAMostrar=ESTADISTICOJUG):
    targColumn = ['A', 'BP', 'BR', 'FP-C', 'FP-F', 'P', 'ppTC', 'R-D', 'R-O', 'REB-T', 'Segs', 'T1-C', 'T1-I', 'T1%',
                  'T2-C', 'T2-I', 'T2%', 'T3-C', 'T3-I', 'T3%', 'TC-I', 'TC-C', 'TC%', 'PTC', 'TAP-C', 'TAP-F']
    result = dict()

    # Campos genéricos
    for col in COLS_IDENTIFIC_JUG:
        auxCount = df[col].value_counts()
        result[col] = auxCount.index[0]

    result['Acta'] = df['enActa'].sum()
    result['Jugados'] = df['haJugado'].sum()
    result['Titular'] = (df['titular'] == 'T').sum()
    result['Vict'] = df['haGanado'].sum()

    df = calcEstadAdicionalesTC(df)

    for col in targColumn:
        auxCol = df[col]

        colAgr = (
            auxCol.mean(), auxCol.median(), auxCol.std(ddof=0), auxCol.max(), auxCol.min(), auxCol.count(),
            auxCol.sum())
        result[col] = colAgr[campoAMostrar]

    result = pd.DataFrame.from_records([result])

    return result


def datosUltimoPartidoJug(tempData: TemporadaACB, df, colTime='Fecha'):
    df = calcEstadAdicionalesTC(df)
    maxVal = df[colTime].max()

    df['Partido'] = df.apply(lambda p: auxEtiqPartido(tempData, p['CODrival'], esLocal=p['esLocal']), axis=1)

    return df.loc[df[colTime] == maxVal]


def datosJugadores(tempData: TemporadaACB, abrEq, partJug):
    COLS_TRAYECT_TEMP = ['Acta', 'Jugados', 'Titular', 'Vict']
    COLS_FICHA = ['id', 'alias', 'posicion', 'altura', 'licencia']
    abrevsEq = tempData.Calendario.abrevsEquipo(abrEq)
    keyDorsal = lambda d: -1 if d == '00' else int(d)

    auxDF = pd.concat([p.jugadoresAdataframe() for p in partJug])
    jugDF = auxDF.loc[auxDF['CODequipo'].isin(abrevsEq)]

    fichasJugadores = tempData.dataFrameFichasJugadores()
    fichasJugadores.posicion = fichasJugadores.posicion.map(TRADPOSICION)

    estadsMedia = jugDF.groupby('codigo').apply(
        lambda c: calcEstadisticasJugador(c, campoAMostrar=ESTADISTICOJUG)).droplevel(1, axis=0)
    estadsTotales = jugDF.groupby('codigo').apply(
        lambda c: calcEstadisticasJugador(c, campoAMostrar=ESTAD_SUMA)).droplevel(1, axis=0)
    # Los porcentajes no suman por lo que hay que volver a calcularlos
    estadsTotales = calcEstadAdicionalesTC(estadsTotales)
    datosUltPart = jugDF.groupby('codigo').apply(lambda c: datosUltimoPartidoJug(tempData, c)).droplevel(1, axis=0)

    identifJug = pd.concat([estadsTotales[COLS_IDENTIFIC_JUG], fichasJugadores[COLS_FICHA]], axis=1, join="inner")
    trayectTemp = estadsTotales[COLS_TRAYECT_TEMP]

    dataFramesAJuntar = {'Jugador': identifJug, 'Trayectoria': trayectTemp,
                         'Promedios': estadsMedia.drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP),
                         'Totales': estadsTotales.drop(columns=COLS_IDENTIFIC_JUG + COLS_TRAYECT_TEMP),
                         'UltimoPart': datosUltPart.drop(columns=COLS_IDENTIFIC_JUG)}
    result = pd.concat(dataFramesAJuntar.values(), axis=1, join='outer', keys=dataFramesAJuntar.keys()).sort_values(
        ('Jugador', 'dorsal'), key=lambda c: c.map(keyDorsal))
    return result


def datosTablaLiga(tempData: TemporadaACB):
    FONTSIZE = 10
    CELLPAD = 3 * mm

    estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                              alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
    ESTILOS.add(estCelda)

    # Precalcula el contenido de la tabla
    auxTabla = defaultdict(dict)
    for jId, jDatos in tempData.Calendario.Jornadas.items():
        for part in jDatos['partidos']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part
        for part in jDatos['pendientes']:
            idLocal = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Local']['abrev']])[0]
            idVisitante = list(tempData.Calendario.tradEquipos['c2i'][part['equipos']['Visitante']['abrev']])[0]
            auxTabla[idLocal][idVisitante] = part

    # En la clasificación está el contenido de los márgenes, de las diagonales y el orden de presentación
    # de los equipos
    clasif = tempData.clasifLiga()
    seqIDs = [(pos, list(equipo['idEq'])[0]) for pos, equipo in enumerate(clasif)]

    datosTabla = []
    cabFila = [Paragraph('<b>Casa/Fuera</b>', style=estCelda)] + [
        Paragraph('<b>' + list(clasif[pos]['abrevsEq'])[0] + '</b>', style=estCelda) for pos, _ in seqIDs] + [
                  Paragraph('<b>Como local</b>', style=estCelda)]
    datosTabla.append(cabFila)
    for pos, idLocal in seqIDs:
        fila = []
        nombreCorto = sorted(clasif[pos]['nombresEq'], key=lambda n: len(n))[0]
        abrev = list(clasif[pos]['abrevsEq'])[0]
        fila.append(Paragraph(f"{nombreCorto} (<b>{abrev}</b>)", style=estCelda))
        for _, idVisit in seqIDs:
            if idLocal != idVisit:
                part = auxTabla[idLocal][idVisit]
                fecha = part['fecha'].strftime("%d-%m") if (('fecha' in part) and (part['fecha'] != NEVER)) else 'TBD'
                jornada = part['jornada']

                texto = f"J:{jornada}<br/>@{fecha}"
                if not part['pendiente']:
                    pURL = part['url']
                    pTempFecha = tempData.Partidos[pURL].fechaPartido
                    fecha =  pTempFecha.strftime("%d-%m")
                    pLocal = part['equipos']['Local']['puntos']
                    pVisit = part['equipos']['Visitante']['puntos']
                    texto = f"J:{jornada}<br/><b>{pLocal}-{pVisit}</b>"
            else:
                auxTexto = auxCalculaBalanceStr(clasif[pos])
                texto = f"<b>{auxTexto}</b>"
            fila.append(Paragraph(texto, style=estCelda))

        fila.append(Paragraph(auxCalculaBalanceStr(clasif[pos]['CasaFuera']['Local']), style=estCelda))
        datosTabla.append(fila)

    filaBalFuera = [Paragraph('<b>Como visitante</b>', style=estCelda)]
    for pos, idLocal in seqIDs:
        filaBalFuera.append(Paragraph(auxCalculaBalanceStr(clasif[pos]['CasaFuera']['Visitante']), style=estCelda))
    filaBalFuera.append([])
    datosTabla.append(filaBalFuera)

    return datosTabla


def listaEquipos(tempData):
    print("Abreviatura -> nombre(s) equipo")
    for abr in sorted(tempData.Calendario.tradEquipos['c2n']):
        listaEquiposAux = sorted(tempData.Calendario.tradEquipos['c2n'][abr], key=lambda x: (len(x), x), reverse=True)
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

    while (len(partsIzdaAux) > 0) or (len(partsDchaAux) > 0):
        bloque = dict()

        try:
            priPartIzda = partsIzdaAux[0]
        except IndexError:
            bloque['J'] = partsDchaAux[0].Jornada
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
            lineas.append(bloque)
            continue
        try:
            priPartDcha = partsDchaAux[0]
        except IndexError:
            bloque['J'] = priPartIzda.Jornada
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            lineas.append(bloque)
            continue

        bloque = dict()
        if priPartIzda.Jornada == priPartDcha.Jornada:
            bloque['J'] = priPartIzda.Jornada
            bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)
        else:
            if (priPartIzda.fechaPartido, priPartIzda.Jornada) < (priPartDcha.fechaPartido, priPartDcha.Jornada):
                bloque['J'] = priPartIzda.Jornada
                bloque['izda'] = partidoTrayectoria(partsIzdaAux.pop(0), abrevsIzda, tempData)
            else:
                bloque['J'] = priPartDcha.Jornada
                bloque['dcha'] = partidoTrayectoria(partsDchaAux.pop(0), abrevsDcha, tempData)

        lineas.append(bloque)

    return lineas


def paginasJugadores(tempData, abrEqs, juIzda, juDcha):
    result = []

    if len(juIzda):
        datosIzda = datosJugadores(tempData, abrEqs[0], juIzda)
        tablasJugadIzda = tablaJugadoresEquipo(datosIzda)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())
        for t in tablasJugadIzda:
            result.append(Spacer(100 * mm, 1 * mm))
            result.append(t)

    if len(juDcha):
        datosIzda = datosJugadores(tempData, abrEqs[1], juDcha)
        tablasJugadIzda = tablaJugadoresEquipo(datosIzda)

        result.append(NextPageTemplate('apaisada'))
        result.append(PageBreak())
        for t in tablasJugadIzda:
            result.append(Spacer(100 * mm, 1 * mm))
            result.append(t)

    return result


def partidoTrayectoria(partido, abrevs, datosTemp):
    # Cadena de información del partido
    strFecha = partido.fechaPartido.strftime("%d-%m")
    abrEq = list(abrevs.intersection(partido.DatosSuministrados['participantes']))[0]
    abrRival = list(partido.DatosSuministrados['participantes'].difference(abrevs))[0]
    locEq = partido.DatosSuministrados['abrev2loc'][abrEq]
    locRival = OtherTeam(locEq)
    textRival = auxEtiqPartido(datosTemp, abrRival, locEq=locEq, usaLargo=False)
    clasifAux = datosTemp.clasifEquipo(abrRival, partido.fechaPartido)
    clasifStr = auxCalculaBalanceStr(clasifAux)
    strRival = f"{strFecha}: {textRival} ({clasifStr})"

    # Cadena del resultado del partido
    # TODO: Esto debería ir en HTML o Markup correspondiente
    prefV = {loc: ('<b>', '</b>') if partido.DatosSuministrados['equipos'][loc]['haGanado'] else ('', '') for loc in
             LocalVisitante}
    prefMe = {loc: ('<u>', '</u>') if (loc == locEq) else ('', '') for loc in LocalVisitante}
    resAux = [
        f"{prefV[loc][0]}{prefMe[loc][0]}{partido.DatosSuministrados['resultado'][loc]}{prefMe[loc][1]}{prefV[loc][1]}"
        for
        loc in LocalVisitante]
    strResultado = "-".join(resAux) + (" (V)" if partido.DatosSuministrados['equipos'][locEq]['haGanado'] else " (D)")

    return strRival, strResultado


def reportTrayectoriaEquipos(tempData, abrEqs, juIzda, juDcha):
    listaTrayectoria = datosMezclaPartJugados(tempData, abrEqs, juIzda, juDcha)
    filas = []

    resultStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=12, align='center')
    cellStyle = ParagraphStyle('trayStyle', fontName='Helvetica', fontSize=12)
    jornStyle = ParagraphStyle('trayStyle', fontName='Helvetica-Bold', fontSize=13, align='right')

    for f in listaTrayectoria:
        datosIzda = f.get('izda', ['', ''])
        datosDcha = f.get('dcha', ['', ''])
        jornada = f['J']

        aux = [Paragraph(f"<para align='center'>{datosIzda[1]}</para>"),
               Paragraph(f"<para>{datosIzda[0]}</para>"),
               Paragraph(f"<para align='center' fontName='Helvetica-Bold'>{str(jornada)}</para>"),
               Paragraph(f"<para>{datosDcha[0]}</para>"),
               Paragraph(f"<para align='center'>{datosDcha[1]}</para>")]
        filas.append(aux)

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black)])

    t = Table(data=filas, style=tStyle, colWidths=[23 * mm, 72 * mm, 10 * mm, 72 * mm, 23 * mm])

    return t


def tablaJugadoresEquipo(jugDF):
    result = []

    CELLPAD = 0.2 * mm
    FONTSIZE = 8
    ANCHOLETRA = FONTSIZE * 0.5

    COLSIDENT = [('Jugador', 'dorsal'),
                 ('Jugador', 'nombre'),
                 ('Trayectoria', 'Acta'),
                 ('Trayectoria', 'Jugados'),
                 ('Trayectoria', 'Titular'),
                 ('Trayectoria', 'Vict')
                 ]
    COLSIDENT_UP = [('Jugador', 'dorsal'),
                    ('Jugador', 'nombre'),
                    ]

    COLS_PROMED = [('Promedios', 'etSegs'),
                   ('Promedios', 'P'),
                   ('Promedios', 'etiqT2'),
                   ('Promedios', 'etiqT3'),
                   ('Promedios', 'etiqTC'),
                   ('Promedios', 'ppTC'),
                   ('Promedios', 'FP-F'),
                   ('Promedios', 'FP-C'),
                   ('Promedios', 'etiqT1'),
                   ('Promedios', 'etRebs'),
                   ('Promedios', 'A'),
                   ('Promedios', 'BP'),
                   ('Promedios', 'BR'),
                   ('Promedios', 'TAP-F'),
                   ('Promedios', 'TAP-C'),
                   ]
    COLS_TOTALES = [
        ('Totales', 'etSegs'),
        ('Totales', 'P'),
        ('Totales', 'etiqT2'),
        ('Totales', 'etiqT3'),
        ('Totales', 'etiqTC'),
        ('Totales', 'ppTC'),
        ('Totales', 'FP-F'),
        ('Totales', 'FP-C'),
        ('Totales', 'etiqT1'),
        ('Totales', 'etRebs'),
        ('Totales', 'A'),
        ('Totales', 'BP'),
        ('Totales', 'BR'),
        ('Totales', 'TAP-F'),
        ('Totales', 'TAP-C'),
    ]
    COLS_ULTP = [('UltimoPart', 'etFecha'),
                 ('UltimoPart', 'Partido'),
                 ('UltimoPart', 'resultado'),
                 ('UltimoPart', 'titular'),
                 ('UltimoPart', 'etSegs'),
                 ('UltimoPart', 'P'),
                 ('UltimoPart', 'etiqT2'),
                 ('UltimoPart', 'etiqT3'),
                 ('UltimoPart', 'etiqTC'),
                 ('UltimoPart', 'ppTC'),
                 ('UltimoPart', 'FP-F'),
                 ('UltimoPart', 'FP-C'),
                 ('UltimoPart', 'etiqT1'),
                 ('UltimoPart', 'etRebs'),
                 ('UltimoPart', 'A'),
                 ('UltimoPart', 'BP'),
                 ('UltimoPart', 'BR'),
                 ('UltimoPart', 'TAP-F'),
                 ('UltimoPart', 'TAP-C'),
                 ]

    baseOPS = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
               ('ALIGN', (0, 0), (-1, 0), 'CENTER'), ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
               ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
               ('LEADING', (0, 0), (-1, -1), FONTSIZE + 1), ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD),
               ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD), ('TOPPADDING', (0, 0), (-1, -1), CELLPAD),
               ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD), ]

    auxDF = jugDF.copy()

    for colList in [(COLSIDENT + COLS_PROMED), (COLSIDENT + COLS_TOTALES),
                    (COLSIDENT_UP + COLS_ULTP)]:  # , [COLSIDENT +COLS_TOTALES], [COLSIDENT +COLS_ULTP]
        t = auxGeneraTabla(auxDF, colList, INFOTABLAJUGS, baseOPS, FORMATOCAMPOS, ANCHOLETRA)

        result.append(t)

    return result


def tablaLiga(tempData: TemporadaACB):
    CELLPAD = 0.3 * mm
    FONTSIZE = 10

    tStyle = TableStyle([('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                         ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                         ('GRID', (0, 0), (-1, -1), 0.5, colors.black), ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE),
                         ('LEADING', (0, 0), (-1, -1), FONTSIZE), ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD),
                         ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD), ('TOPPADDING', (0, 0), (-1, -1), CELLPAD),
                         ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD), ])
    datosAux = datosTablaLiga(tempData)

    t = Table(datosAux, style=tStyle)

    return t


def preparaLibro(outfile, tempData, datosSig):
    MARGENFRAME = 2 * mm
    frameNormal = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[0] - 2 * MARGENFRAME, height=A4[1] - 2 * MARGENFRAME,
                        leftPadding=MARGENFRAME,
                        bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME, topPadding=MARGENFRAME)
    frameApaisado = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[1] - 2 * MARGENFRAME, height=A4[0] - 2 * MARGENFRAME,
                          leftPadding=MARGENFRAME,
                          bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME, topPadding=MARGENFRAME)
    pagNormal = PageTemplate('normal', pagesize=A4, frames=[frameNormal], autoNextPageTemplate='normal')
    pagApaisada = PageTemplate('apaisada', pagesize=landscape(A4), frames=[frameApaisado],
                               autoNextPageTemplate='apaisada')

    doc = SimpleDocTemplate(filename=outfile, pagesize=A4, bottomup=0, verbosity=4, initialFontName='Helvetica',
                            initialLeading=5 * mm,
                            leftMargin=5 * mm,
                            rightMargin=5 * mm,
                            topMargin=5 * mm,
                            bottomMargin=5 * mm, )
    doc.addPageTemplates([pagNormal, pagApaisada])

    story = []

    (sigPartido, abrEqs, juIzda, peEq, juDcha, peRiv, targLocal) = datosSig

    antecedentes = {p.url for p in juIzda}.intersection({p.url for p in juDcha})

    story.append(cabeceraPortada(sigPartido, tempData))

    story.append(Spacer(width=120 * mm, height=2 * mm))
    story.append(estadsEquipoPortada(tempData, abrEqs))

    if antecedentes:
        print("Antecedentes!")
    else:
        story.append(Spacer(width=120 * mm, height=3 * mm))
        story.append(Paragraph("Sin antecedentes esta temporada"))

    trayectoria = reportTrayectoriaEquipos(tempData, abrEqs, juIzda, juDcha)
    if trayectoria:
        story.append(Spacer(width=120 * mm, height=3 * mm))
        story.append(trayectoria)

    story.append(NextPageTemplate('apaisada'))
    story.append(PageBreak())
    story.append(tablaLiga(tempData))

    if (len(juIzda) or len(juDcha)):
        infoJugadores = paginasJugadores(tempData, abrEqs, juIzda, juDcha)
        story.extend(infoJugadores)

    doc.build(story)


def parse_arguments():
    descriptionTXT = "Prepares a booklet for the next game of a team"

    parser = ArgumentParser(description=descriptionTXT)
    parser.add_argument("-t", "--acbfile", dest="acbfile", action="store", required=True, env_var="ACB_FILE",
                        help="Nombre del ficheros de temporada", )
    parser.add_argument("-l", "--listaequipos", dest='listaEquipos', action="store_true", required=False,
                        help="Lista siglas para equipos", )

    parser.add_argument("-e", "--equipo", dest="equipo", action="store", required=False,
                        help="Abreviatura del equipo deseado (usar -l para obtener lista)", )
    parser.add_argument("-o", "--outfile", dest="outfile", action="store", help="Fichero PDF generado",
                        required=False, )

    parser.add_argument("-c", "--cachedir", dest="cachedir", action="store", required=False, env_var="ACB_CACHEDIR",
                        help="Ubicación de caché de ficheros", )

    result = parser.parse_args()

    return result


def main(args):
    tempData = cargaTemporada(args.acbfile)

    if args.listaEquipos:
        listaEquipos(tempData)

    REQARGS = ['equipo', 'outfile']
    missingReqs = {k for k in REQARGS if (k not in args) or (args.__getattribute__(k) is None)}
    if missingReqs:
        missingReqsStr = ",".join(sorted(missingReqs))
        print(f"Faltan argumentos (ver -h): {missingReqsStr}")
        sys.exit(1)
    try:
        datosSig = tempData.sigPartido(args.equipo)
    except KeyError as exc:
        print(f"Equipo desconocido '{args.equipo}': {exc}")
        sys.exit(1)

    preparaLibro(args.outfile, tempData, datosSig)


if __name__ == '__main__':
    args = parse_arguments()
    main(args)

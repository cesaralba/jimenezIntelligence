from itertools import product
from operator import itemgetter
from typing import Set, Optional, List, Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, TableStyle, Table

import SMACB.Programa.Globals as GlobACB
from SMACB.Constants import infoSigPartido, LocalVisitante, MARCADORESCLASIF, RANKFORMAT
from SMACB.Programa.Constantes import (ESTADISTICOEQ, estiloNegBal, estiloPosMarker, colEq, DEFTABVALUE, FORMATOCAMPOS,
                                       colorTablaDiagonal, ANCHOMARCAPOS)
from SMACB.Programa.Datos import datosRestoJornada
from SMACB.Programa.FuncionesAux import auxCalculaBalanceStr, auxJugsBajaTablaJugs, GENERADORCLAVEDORSAL, \
    GENERADORFECHA, GENMAPDICT, GENERADORTIEMPO, GENERADORETTIRO, GENERADORETREBOTE, auxBold, equipo2clasif, \
    auxLabelEqTabla, auxCruceDiag, auxCruceTotalPend, auxCruceTotalResuelto, auxCruceResuelto, auxCrucePendiente, \
    auxCruceTotales, auxLigaDiag, auxTablaLigaPartJugado, auxTablaLigaPartPendiente
from SMACB.Programa.Globals import recuperaClasifLiga, recuperaEstadsGlobales
from SMACB.TemporadaACB import TemporadaACB, extraeCampoYorden
from Utils.ReportLab.RLverticalText import VerticalParagraph

ESTILOS = getSampleStyleSheet()

sentinel = object()


def datosEstadsBasicas(tempData: TemporadaACB, infoEq: dict):
    recuperaEstadsGlobales(tempData)

    abrev = infoEq['abrev']
    nombreCorto = infoEq.get('nombcorto', abrev)

    targAbrev = list(tempData.Calendario.abrevsEquipo(abrev).intersection(GlobACB.estadGlobales.index))[0]
    if not targAbrev:
        valCorrectos = ", ".join(sorted(GlobACB.estadGlobales.index))
        raise KeyError(f"extraeCampoYorden: equipo (abr) '{abrev}' desconocido. Equipos validos: {valCorrectos}")

    estadsEq = GlobACB.estadGlobales.loc[targAbrev]
    estadsEqOrden = GlobACB.estadGlobalesOrden.loc[targAbrev]

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


def tablaRestoJornada(tempData: TemporadaACB, datosSig: infoSigPartido):
    def infoEq(eqData: dict, jornada: int, jornadasCompletas: Set[int] = sentinel):
        abrev = eqData['abrev']

        clasifAux = equipo2clasif(GlobACB.clasifLiga, abrev)
        clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=jornada, addPendJornada=False,
                                         jornadasCompletas=jornadasCompletas)
        formatoIn, formatoOut = ('<b>', '</b>') if eqData['haGanado'] else ('', '')
        formato = "{fIn}{nombre}{fOut} [{balance}]"
        result = formato.format(nombre=eqData['nombcorto'], balance=clasifStr, fIn=formatoIn, fOut=formatoOut)
        return result

    def infoRes(partData: dict):
        pts = []
        for loc in LocalVisitante:
            p = partData['resultado'][loc]
            formato = "<b>{:3}</b>" if partData['equipos'][loc]['haGanado'] else "{:3}"
            pts.append(formato.format(p))
        result = "-".join(pts)
        return result

    def etFecha(tStamp: pd.Timestamp, fechaRef: pd.Timestamp = None):
        tFormato = "%d-%m-%Y"
        if fechaRef and abs((tStamp - fechaRef).days) <= 3:
            tFormato = "%a %d@%H:%M"
        result = tStamp.strftime(tFormato)
        return result

    def preparaDatos(datos, tstampRef, jornadasCompletas: Set[int] = sentinel):
        intData = []
        for p in sorted(datos, key=itemgetter('fechaPartido')):
            info = {'pendiente': p['pendiente'], 'fecha': etFecha(p['fechaPartido'], tstampRef)}
            for loc in LocalVisitante:
                info[loc] = infoEq(p['equipos'][loc], jornada=jornada, jornadasCompletas=jornadasCompletas)
            if not p['pendiente']:
                info['resultado'] = infoRes(p)

            intData.append(info)
        return intData

    # Data preparation
    sigPartido = datosSig.sigPartido
    jornada = int(sigPartido['jornada'])
    recuperaClasifLiga(tempData)
    drj = datosRestoJornada(tempData, datosSig)
    datosParts = preparaDatos(drj, sigPartido['fechaPartido'], jornadasCompletas=tempData.jornadasCompletas())

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


def bloqueCabEquipo(datosEq, tempData, fecha, currJornada: int = None):
    recuperaClasifLiga(tempData, fecha)
    # TODO: Imagen (descargar imagen de escudo y plantarla)
    nombre = datosEq['nombcorto']

    clasifAux = equipo2clasif(GlobACB.clasifLiga, datosEq['abrev'])
    clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=currJornada,
                                     jornadasCompletas=tempData.jornadasCompletas())

    result = [Paragraph(f"<para align='center' fontSize='16' leading='17'><b>{nombre}</b></para>"),
              Paragraph(f"<para align='center' fontSize='14'>{clasifStr}</para>")]

    return result


def auxGeneraLeyendaEstadsJugsCelda(leyendaTxt: str):
    legendStyle = ParagraphStyle('tabJugsLegend', alignment=TA_CENTER, allowWidows=0)
    result = VerticalParagraph(leyendaTxt, style=legendStyle)
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
        formatos = {}

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


def tablasJugadoresEquipo(jugDF, abrev: Optional[str] = None, tablasIncluidas: List[str] = sentinel):
    if tablasIncluidas is sentinel:
        tablasIncluidas = []

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

    tablas = {'PROMEDIOS': {'seq': 1, 'nombre': 'Promedios', 'columnas': (COLSIDENT_PROM + COLS_PROMED),
                            'extraCols': [('Jugador', 'Kdorsal')], 'filtro': [(COLACTIVO, True)],
                            'ordena': [(COLDORSAL_IDX, True)]},
              'TOTALES': {'seq': 2, 'nombre': 'Totales', 'columnas': (COLSIDENT_TOT + COLS_TOTALES),
                          'extraCols': [('Jugador', 'Kdorsal')], 'ordena': [(COLACTIVO, False), (COLDORSAL_IDX, True)]},
              'ULTIMOPARTIDO': {'seq': 3, 'nombre': 'Último partido', 'columnas': (COLSIDENT_UP + COLS_ULTP),
                                'extraCols': [('Jugador', 'Kdorsal')], 'filtro': [(COLACTIVO, True)],
                                'ordena': [(COLDORSAL_IDX, True)]}}
    auxDF = jugDF.copy()

    for claveTabla in tablasIncluidas:
        infoTabla = tablas[claveTabla]  # , [COLSIDENT +COLS_TOTALES], [COLSIDENT +COLS_ULTP]
        t = auxGeneraTablaJugs(auxDF, claveTabla, infoTabla, INFOTABLAJUGS, baseOPS, FORMATOCAMPOS, ANCHOLETRA,
                               repeatRows=1, abrev=abrev)

        result.append((infoTabla, t))

    return result


def auxGeneraLeyendaEstadsCelda(leyenda: dict, FONTSIZE: int, listaEqs: Iterable):
    legendStyle = ParagraphStyle('tabEstadsLegend', fontSize=FONTSIZE, alignment=TA_JUSTIFY, wordWrap=True,
                                 leading=10, )

    separador = "<center>---</center><br/>"
    textoEncab = """
<b>Mejor</b>: Primero en el ranking<br/>
<b>ACB</b>: Media de la liga (+- desv estándar)<br/>
<b>Peor</b>: Último en el ranking<br/>
    """

    textoEtEqs = """
<b>Equipo</b>: Valores conseguidos por el equipo<br/>
<b>Rival</b>: Valores conseguidos por el rival<br/>
    """
    textoCD = """
<b>[C]</b>: <i>Mejor</i> cuanto menor<br/>
<b>[D]</b>: <i>Mejor</i> cuanto mayor<br/>
    """
    textoEstads = "".join(
        [f"<b>{k.replace(' ', '&nbsp;')}</b>:&nbsp;{leyenda[k]}<br/>" for k in sorted(leyenda.keys())])

    textoEqs = "".join([f"<b>{abr.replace(' ', '&nbsp;')}</b>:&nbsp;{GlobACB.tradEquipos['a2n'][abr]}<br/>" for abr in
                        sorted(listaEqs)])

    textoCompleto = separador.join([textoEtEqs, textoCD, textoEncab, textoEstads, textoEqs])
    result = Paragraph(textoCompleto, style=legendStyle)
    return result


ANCHOTIROS = 16
ANCHOREBOTES = 14
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


def auxFilasTablaEstadisticos(datosAmostrar: dict, clavesEquipo: list | None = None, clavesRival: list | None = None,
                              estiloCelda: ParagraphStyle = None, estiloCabCelda: ParagraphStyle = None
                              ) -> (list, dict):
    result = []
    leyendas = {}
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


def presTablaCruces(data, FONTSIZE=9, CELLPAD=3 * mm):
    ancho = 2 + len(data['equipos'])
    alto = 2 + len(data['equipos'])

    if 'celTabLiga' not in ESTILOS:
        estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                                  alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
        ESTILOS.add(estCelda)
    else:
        estCelda = ESTILOS.get('celTabLiga')

    result = [[Paragraph('', style=estCelda)] * alto for _ in range(ancho)]
    result[0][0] = Paragraph('', style=estCelda)
    result[0][-1] = Paragraph('<b>Total Res</b>', style=estCelda)
    result[-1][0] = Paragraph('<b>Total Pend</b>', style=estCelda)

    result[-1][-1] = Paragraph(auxCruceTotales(data['datosTotales']), style=estCelda)  # , clavesAmostrar

    datosDiag = data['datosDiagonal']
    datosCont = data['datosContadores']
    for eq in data['equipos']:
        pos = eq.pos
        abrev = eq.abrev

        result[pos][0] = Paragraph(auxLabelEqTabla(eq.nombre, abrev), style=estCelda)
        result[0][pos] = Paragraph(auxBold(abrev), style=estCelda)
        result[pos][pos] = Paragraph(auxCruceDiag(datosDiag[abrev], ponBal=True, ponDif=True), style=estCelda)
        result[-1][pos] = Paragraph(auxCruceTotalPend(datosCont[abrev]), style=estCelda)
        result[pos][-1] = Paragraph(auxCruceTotalResuelto(datosCont[abrev], data['clavesAmostrar']), style=estCelda)

    for crucePend in data['resueltos']:
        coords = sorted([datosDiag[abr]['pos'] for abr in [crucePend[0], crucePend[1]]], reverse=False)
        result[coords[0]][coords[1]] = Paragraph(auxCruceResuelto(crucePend[2]), style=estCelda)
    for crucePend in data['pendientes']:
        coords = sorted([datosDiag[abr]['pos'] for abr in [crucePend[0], crucePend[1]]], reverse=True)
        result[coords[0]][coords[1]] = Paragraph(auxCrucePendiente(crucePend[2]), style=estCelda)

    return result


def presTablaCrucesEstilos(data, FONTSIZE=9, CELLPAD=3 * mm):
    firstNegBal = data['firstNegBal']

    listaEstilos = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (0, 0), (-1, -1), FONTSIZE),
                    ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
                    ('TOPPADDING', (0, 0), (-1, -1), CELLPAD), ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD),
                    ("BACKGROUND", (-1, 1), (-1, -2), colors.lightgrey),
                    ("BACKGROUND", (1, -1), (-2, -1), colors.lightgrey)]

    # Diagonal
    for i in range(1, len(data['equipos']) + 1):
        listaEstilos.append(("BACKGROUND", (i, i), (i, i), colorTablaDiagonal))

    auxListaPosMarkers = []
    for pos in MARCADORESCLASIF:
        auxEstilo = estiloNegBal if (firstNegBal and pos == (firstNegBal - 1)) else estiloPosMarker
        auxListaPosMarkers.append((pos, auxEstilo))
    if (firstNegBal and (firstNegBal - 1) not in MARCADORESCLASIF):
        auxListaPosMarkers.append((firstNegBal - 1, estiloNegBal))
    for pos, resto in auxListaPosMarkers:
        commH, commV, incr = ("LINEBELOW", "LINEAFTER", 0) if pos >= 0 else ("LINEABOVE", "LINEBEFORE", -1)
        posIni, posFin = (0, pos + incr) if pos >= 0 else (pos + incr, -1)

        listaEstilos.append([commH, (posIni, pos + incr), (posFin, pos + incr), ANCHOMARCAPOS] + resto)
        listaEstilos.append([commV, (pos + incr, posIni), (pos + incr, posFin), ANCHOMARCAPOS] + resto)
    #
    # # Marca los partidos del tipo (jugados o pendientes) que tenga menos
    # claveJuPe = 'ju' if len(coordsJuPe['ju']) <= len(coordsJuPe['pe']) else 'pe'
    # CANTGREYJUPE = .90
    # colP = colors.rgb2cmyk(CANTGREYJUPE, CANTGREYJUPE, CANTGREYJUPE)
    # for x, y in coordsJuPe[claveJuPe]:
    #     coord = (y + 1, x + 1)
    #     listaEstilos.append(("BACKGROUND", coord, coord, colP))
    #
    # if equiposAmarcar is not None:
    #     parEqs = set(listize(equiposAmarcar))
    #     seqIDs = [(pos, equipo.abrevsEq) for pos, equipo in enumerate(GlobACB.clasifLiga) if
    #               equipo.abrevsEq.intersection(parEqs)]
    #     for pos, _ in seqIDs:
    #         listaEstilos.append(("BACKGROUND", (pos + 1, 0), (pos + 1, 0), colEq))
    #         listaEstilos.append(("BACKGROUND", (0, pos + 1), (0, pos + 1), colEq))
    return listaEstilos


def presTablaPartidosLigaReg(data, FONTSIZE=9, CELLPAD=3 * mm):
    ancho = 2 + len(data['equipos'])
    alto = 2 + len(data['equipos'])

    if 'celTabLiga' not in ESTILOS:
        estCelda = ParagraphStyle('celTabLiga', ESTILOS.get('Normal'), fontSize=FONTSIZE, leading=FONTSIZE,
                                  alignment=TA_CENTER, borderPadding=CELLPAD, spaceAfter=CELLPAD, spaceBefore=CELLPAD)
        ESTILOS.add(estCelda)
    else:
        estCelda = ESTILOS.get('celTabLiga')

    result = [[Paragraph('', style=estCelda)] * alto for _ in range(ancho)]
    result[0][0] = Paragraph('Casa/Fuera', style=estCelda)
    result[0][-1] = Paragraph('Como local', style=estCelda)
    result[-1][0] = Paragraph('Como visitante', style=estCelda)

    result[-1][-1] = Paragraph(
        f'J:{(100 * len(data['jugados']) / (len(data['pendientes']) + len(data['jugados']))):.2g}%',
        style=estCelda)  # , clavesAmostrar

    datosDiag = data['datosDiagonal']

    for eq in data['equipos']:
        pos = eq.pos
        abrev = eq.abrev

        result[pos][0] = Paragraph(auxLabelEqTabla(eq.nombre, abrev), style=estCelda)
        result[0][pos] = Paragraph(auxBold(abrev), style=estCelda)
        result[pos][pos] = Paragraph(auxBold(auxLigaDiag(datosDiag[abrev], ponBal=True, ponSuf=True)), style=estCelda)
        result[-1][pos] = Paragraph((datosDiag[abrev]['balanceVisitante']), style=estCelda)
        result[pos][-1] = Paragraph((datosDiag[abrev]['balanceLocal']), style=estCelda)

    for part in data['jugados']:
        coords = [datosDiag[abr]['pos'] for abr in [part[0], part[1]]]
        result[coords[0]][coords[1]] = Paragraph(auxTablaLigaPartJugado(part), style=estCelda)

    for part in data['pendientes']:
        coords = [datosDiag[abr]['pos'] for abr in [part[0], part[1]]]
        result[coords[0]][coords[1]] = Paragraph(auxTablaLigaPartPendiente(part), style=estCelda)

    return result


def presTablaPartidosLigaRegEstilos(data, equiposAmarcar: Optional[Iterable[str]] = None, FONTSIZE=9, CELLPAD=3 * mm):
    listaEstilos = [('BOX', (0, 0), (-1, -1), 2, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), FONTSIZE), ('LEADING', (0, 0), (-1, -1), FONTSIZE),
                    ('LEFTPADDING', (0, 0), (-1, -1), CELLPAD), ('RIGHTPADDING', (0, 0), (-1, -1), CELLPAD),
                    ('TOPPADDING', (0, 0), (-1, -1), CELLPAD), ('BOTTOMPADDING', (0, 0), (-1, -1), CELLPAD),
                    ("BACKGROUND", (-1, 1), (-1, -2), colors.lightgrey),
                    ("BACKGROUND", (1, -1), (-2, -1), colors.lightgrey)]

    # Diagonal
    for i in range(1, len(data['equipos']) + 1):
        listaEstilos.append(("BACKGROUND", (i, i), (i, i), colorTablaDiagonal))

    auxListaPosMarkers = []
    for pos in MARCADORESCLASIF:
        auxEstilo = estiloNegBal if (data['firstNegBal'] and pos == (data['firstNegBal'] - 1)) else estiloPosMarker
        auxListaPosMarkers.append((pos, auxEstilo))
    if (data['firstNegBal'] and (data['firstNegBal'] - 1) not in MARCADORESCLASIF):
        auxListaPosMarkers.append((data['firstNegBal'] - 1, estiloNegBal))
    for pos, resto in auxListaPosMarkers:
        commH, commV, incr = ("LINEBELOW", "LINEAFTER", 0) if pos >= 0 else ("LINEABOVE", "LINEBEFORE", -1)
        posIni, posFin = (0, pos + incr) if pos >= 0 else (pos + incr, -1)

        listaEstilos.append([commH, (posIni, pos + incr), (posFin, pos + incr), ANCHOMARCAPOS] + resto)
        listaEstilos.append([commV, (pos + incr, posIni), (pos + incr, posFin), ANCHOMARCAPOS] + resto)

    if equiposAmarcar is not None:
        for pos in [data['datosDiagonal'][abrev]['pos'] for abrev in equiposAmarcar]:
            listaEstilos.append(("BACKGROUND", (pos, 0), (pos, 0), colEq))
            listaEstilos.append(("BACKGROUND", (0, pos), (0, pos), colEq))

    return listaEstilos

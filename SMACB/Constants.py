from babel.numbers import decimal

from Utils.Misc import BadParameters

URL_BASE = "http://www.acb.com"

MAXIMOextranjeros = 2
MINIMOnacionales = 4

PRESUPUESTOinicial = 6500000.0
PRECIOpunto = 70000.0
MINPRECIO = 45000.0

POSICIONES = {'posicion1': 'Base', 'posicion3': 'Alero', 'posicion5': 'Pivot'}
CUPOS = ['Extracomunitario', 'Español', 'normal']

POSICIONCORTA = {'posicion1': 'B', 'posicion3': 'A', 'posicion5': 'P'}
CUPOCORTO = {'Extracomunitario': 'Ext', 'Español': 'Esp', 'normal': 'Com'}

LISTACOMPOS = {'puntos': 'P', 'rebotes': 'REB-T', 'triples': 'T3-C', 'asistencias': 'A'}

BONUSVICTORIA = 1.2

# Orden de busqueda de las claves y de almacenamiento procesado
# SEQCLAVES = ['asistencias', 'triples', 'rebotes', 'puntos', 'valJornada', 'broker']
# SEQCLAVES = ['asistencias', 'rebotes', 'puntos', 'triples', 'valJornada', 'broker']
SEQCLAVES = ['triples', 'asistencias', 'rebotes', 'puntos', 'valJornada', 'broker']

CLAVESCSV = ['solkey', 'grupo', 'jugs', 'valJornada', 'broker', 'puntos', 'rebotes', 'triples', 'asistencias', 'Nones']
bool2esp = {True: "S", False: "N"}
haGanado2esp = {True: "V", False: "D"}
titular2esp = {True: "T", False: "B"}
local2esp = {True: "L", False: "V"}

LocalVisitante = ('Local', 'Visitante')
EqRival = ('Eq', 'Rival')

LOCALNAMES = {'Local', 'L', 'local'}
VISITNAMES = {'Visitante', 'V', 'visitante'}

DESCENSOS = 2
MARCADORESCLASIF = [2, 4, 8, -DESCENSOS]

# 'FP-C' Faltas recibidas, 'FP-F' Faltas cometidas, 'TAP-C' Tapones recibidos, 'TAP-F' Tapones hechos
ALLCATS = {'+/-', 'A', 'A/BP', 'A/TC-C', 'BP', 'BR', 'C', 'DER', 'DERpot', 'EffRebD', 'EffRebO', 'FP-C', 'FP-F', 'M',
           'OER', 'OERpot', 'P', 'PNR', 'POS', 'POStot', 'PTC/PTCPot', 'Priv', 'Ptot', 'R-D', 'R-O', 'REB-T', 'RO/TC-F',
           'Segs', 'T1%', 'T1-C', 'T1-I', 'T2%', 'T2-C', 'T2-I', 'T3%', 'T3-C', 'T3-I', 'TAP-C', 'TAP-F', 'TC%', 'TC-C',
           'TC-I', 'V', 'Vict', 'convocados', 'eff-t2', 'eff-t3', 'haGanado', 'local', 'ppTC', 't2/tc-C', 't2/tc-I',
           't3/tc-C', 't3/tc-I', 'utilizados'}
CATESTADSEQ2IGNORE = {'+/-', 'C', 'convocados', 'haGanado', 'local', 'M', 'Segs', 'utilizados', 'V'}
CATESTADSEQASCENDING = {'DER', 'DERpot', 'Prec', 'BP', 'FP-F', 'TAP-C', 'PNR'}

DEFAULTNUMFORMAT = '{:3.2f}'
RANKFORMAT = '{:2.0f}'
DEFAULTPERCFORMAT = DEFAULTNUMFORMAT + '%'

REPORTLEYENDAS = {'+/-': {'etiq': '+/-', 'leyenda': 'Cambio en la anotación con él en el campo'},
                  'A': {'etiq': 'A', 'leyenda': 'Asistencias'},
                  'A/BP': {'etiq': 'Asist / Perd', 'leyenda': 'Asistencias dadas por balón perdido'},
                  'A/TC-C': {'etiq': '% Can de As', 'leyenda': 'Canastas por cada tiro de campo',
                             'formato': DEFAULTPERCFORMAT}, 'BP': {'etiq': 'BP', 'leyenda': 'Balones perdidos'},
                  'BR': {'etiq': 'BR', 'leyenda': 'Balones robados'}, 'C': {'etiq': 'C', 'leyenda': 'Contraataques'},
                  'convocados': {'etiq': 'Conv', 'leyenda': 'Jugadores en la convocatoria'},
                  'eff-t1': {'etiq': '% Puntos TL', 'leyenda': 'Porcentaje de puntos de tiro libre',
                             'formato': DEFAULTPERCFORMAT},
                  'eff-t2': {'etiq': '% Puntos 2', 'leyenda': 'Porcentaje de puntos por tiro de 2',
                             'formato': DEFAULTPERCFORMAT},
                  'eff-t3': {'etiq': '% Puntos 3', 'leyenda': 'Porcentaje de puntos por tiro de 3',
                             'formato': DEFAULTPERCFORMAT},
                  'EffRebD': {'etiq': 'Ef reb Def', 'leyenda': '% Rebotes defensivos', 'formato': DEFAULTPERCFORMAT},
                  'EffRebO': {'etiq': 'Ef reb Of', 'leyenda': '% Rebotes ofensivos', 'formato': DEFAULTPERCFORMAT},
                  'FP-C': {'etiq': 'FRec', 'leyenda': 'Faltas recibidas'},
                  'FP-F': {'etiq': 'FCom', 'leyenda': 'Faltas cometias'},
                  'haGanado': {'etiq': 'Victorias', 'leyenda': 'Ratio de victorias'},
                  'local': {'etiq': 'Part en casa', 'leyenda': 'Ratio de partidos en casa'},
                  'M': {'etiq': 'Mates', 'leyenda': 'Mates'},
                  'OER': {'etiq': 'Rating Of', 'leyenda': 'Puntos por posesión'},
                  'DER': {'etiq': 'Rating Def', 'leyenda': 'Puntos rec por posesión'},
                  'OERpot': {'etiq': 'OERpot', 'leyenda': 'OERpot'}, 'DERpot': {'etiq': 'DERpot', 'leyenda': 'DERpot'},
                  'P': {'etiq': 'P', 'leyenda': 'Puntos'}, 'Prec': {'etiq': 'P rec', 'leyenda': 'Puntos recibidos'},
                  'PNR': {'etiq': 'BP Prop', 'leyenda': 'Perdidas no robadas'},
                  'POS': {'etiq': 'Pos', 'leyenda': 'Posesiones'},
                  'ppTC': {'etiq': 'Pts cada tiro', 'leyenda': 'Puntos anotados por tiro de campo'},
                  'PTC/PTCPot': {'etiq': '% Pts Pot', 'leyenda': '% Puntos si hubiese entrado todo',
                                 'formato': DEFAULTPERCFORMAT},
                  'R-D': {'etiq': 'Reb Def', 'leyenda': 'Rebotes defensivos'},
                  'R-O': {'etiq': 'Reb Of', 'leyenda': 'Rebotes ofensivos'},
                  'REB-T': {'etiq': 'Reb total', 'leyenda': 'Rebotes totales'},
                  'RO/TC-F': {'etiq': 'RO/TC-F', 'leyenda': 'RO/TC-F'}, 'Segs': {'etiq': 'Segs', 'leyenda': 'Segs'},
                  'T1%': {'etiq': 'T1%', 'leyenda': 'T1%', 'formato': DEFAULTPERCFORMAT},
                  'T1-C': {'etiq': 'T1-C', 'leyenda': 'T1-C'}, 'T1-I': {'etiq': 'T1-I', 'leyenda': 'T1-I'},
                  'T2%': {'etiq': 'T2%', 'leyenda': 'T2%', 'formato': DEFAULTPERCFORMAT},
                  'T2-C': {'etiq': 'T2-C', 'leyenda': 'T2-C'}, 'T2-I': {'etiq': 'T2-I', 'leyenda': 'T2-I'},
                  't2/tc-C': {'etiq': '%Can 2', 'leyenda': '%Canastas de 2pts', 'formato': DEFAULTPERCFORMAT},
                  't2/tc-I': {'etiq': '%Tiros 2', 'leyenda': '%Tiros de 2 pts', 'formato': DEFAULTPERCFORMAT},
                  'T3%': {'etiq': 'T3%', 'leyenda': 'T3%', 'formato': DEFAULTPERCFORMAT},
                  'T3-C': {'etiq': 'T3-C', 'leyenda': 'T3-C'}, 'T3-I': {'etiq': 'T3-I', 'leyenda': 'T3-I'},
                  't3/tc-C': {'etiq': '%Can 3', 'leyenda': '%Canastas de 3pts', 'formato': DEFAULTPERCFORMAT},
                  't3/tc-I': {'etiq': '%Tiros 3', 'leyenda': '%Tiros de 3pts', 'formato': DEFAULTPERCFORMAT},
                  'TAP-C': {'etiq': 'Tap rec', 'leyenda': 'Tapones recibidos'},
                  'TAP-F': {'etiq': 'Tapones', 'leyenda': 'Tapones'},
                  'TC%': {'etiq': 'TC%', 'leyenda': 'TC%', 'formato': DEFAULTPERCFORMAT},
                  'TC-C': {'etiq': 'TC-C', 'leyenda': 'TC-C'}, 'TC-I': {'etiq': 'TC-I', 'leyenda': 'TC-I'},
                  'utilizados': {'etiq': 'Usados', 'leyenda': 'Jugadores utilizados'},
                  'V': {'etiq': 'V', 'leyenda': 'Valoración ACB'}}


def calculaValSuperManager(valoracion, haGanado=False):
    return round(
        decimal.Decimal.from_float(float(valoracion) * (BONUSVICTORIA if (haGanado and (valoracion > 0)) else 1.0)), 2)


def buildPosCupoIndex():
    """
    Genera un diccionario con los índices que corresponden a cada posición y cupo.
    :return:
    """
    indexResult = dict()

    aux = 0
    for pos in POSICIONES:
        indexResult[pos] = dict()
        for cupo in CUPOS:
            indexResult[pos][cupo] = aux
            aux += 1
    return indexResult


def claveGrupo(jornada, index, counters):
    FORMATO = "J%3d-%s"
    return FORMATO % (jornada, "+".join(["%1d_%1d" % (i, c) for i, c in zip(index, counters)]))


def solucion2clave(clave, sol, charsep="#"):
    CLAVESOL = ['valJornada', 'broker', 'puntos', 'asistencias', 'triples', 'rebotes']
    formatos = {'asistencias': "a_%03d", 'triples': "t_%03d", 'rebotes': "r_%03d", 'puntos': "p_%03d",
                'valJornada': "v_%05.2f", 'broker': "b_%010d"}
    formatoTotal = charsep.join([formatos[k] for k in CLAVESOL])
    valores = [sol[k] for k in CLAVESOL]

    return clave + "#" + (formatoTotal % tuple(valores))


def OtherLoc(team):
    if team == 'Local':
        return 'Visitante'
    elif team == 'Visitante':
        return 'Local'
    else:
        raise BadParameters("OtherLoc: '%s' provided. It only accept 'Visitante' or 'Local'" % team)


def OtherTeam(team):
    if team == 'Eq':
        return 'Rival'
    elif team == 'Rival':
        return 'Eq'
    else:
        raise BadParameters("OtherTeam: '%s' provided. It only accept 'Eq' or 'Rival'" % team)

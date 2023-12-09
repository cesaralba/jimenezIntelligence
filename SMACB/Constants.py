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

REPORTLEYENDAS= {'+/-': {'etiq': '+/-', 'leyenda': 'Cambio en la anotación con él en el campo', 'formato': '{.2f}'},
                 'A': {'etiq': 'A', 'leyenda': 'Asistencias', 'formato': '{:.2f}'},
                 'A/BP': {'etiq': 'A/BP', 'leyenda': 'Asistencias dadas por balón perdido', 'formato': '{:.2f}'},
                 'A/TC-C': {'etiq': 'A/TC-C', 'leyenda': 'Canastas por cada tiro de campo', 'formato': '{:.2f}'},
                 'BP': {'etiq': 'BP', 'leyenda': 'Balones perdidos', 'formato': '{:.2f}'},
                 'BR': {'etiq': 'BR', 'leyenda': 'Balones robados', 'formato': '{:.2f}'},
                 'C': {'etiq': 'C', 'leyenda': 'Contraataques', 'formato': '{:.2f}'},
                 'convocados': {'etiq': 'Conv',
                                'leyenda': 'Jugadores en la convocatoria',
                                'formato': '{:.2f}'},
                 'eff-t2': {'etiq': '% Puntos 2', 'leyenda': 'Porcentaje de puntos por tiro de 2', 'formato': '{:.2f}%'},
                 'eff-t3': {'etiq': '% Puntos 3', 'leyenda': 'Porcentaje de puntos por tiro de 3', 'formato': '{:.2f}%'},
                 'EffRebD': {'etiq': 'Efic rebote Def', 'leyenda': '% Rebotes defensivos', 'formato': '{:.2f}%'},
                 'EffRebO': {'etiq': 'Efic rebote Of', 'leyenda': '% Rebotes ofensivos', 'formato': '{:.2f}%'},
                 'FP-C': {'etiq': 'FRec', 'leyenda': 'Faltas recibidas', 'formato': '{:.2f}'},
                 'FP-F': {'etiq': 'FCom', 'leyenda': 'Faltas cometias', 'formato': '{:.2f}'},
                 'haGanado': {'etiq': 'Victorias', 'leyenda': 'Ratio de victorias', 'formato': '{:.2f}'},
                 'local': {'etiq': 'Part en casa', 'leyenda': 'Ratio de partidos en casa', 'formato': '{:.2f}'},
                 'M': {'etiq': 'Mates', 'leyenda': 'Mates', 'formato': '{:.2f}'},
                 'OER': {'etiq': 'Rating Of', 'leyenda': 'Puntos por posesión', 'formato': '{:.2f}'},
                 'OERpot': {'etiq': 'OERpot', 'leyenda': 'OERpot', 'formato': '{:.2f}'},
                 'P': {'etiq': 'P', 'leyenda': 'Puntos', 'formato': '{:.2f}'},
                 'PNR': {'etiq': 'BP Prop', 'leyenda': 'Perdidas no robadas', 'formato': '{:.2f}'},
                 'POS': {'etiq': 'Pos', 'leyenda': 'Posesiones', 'formato': '{:.2f}'},
                 'ppTC': {'etiq': 'ppTC', 'leyenda': 'ppTC', 'formato': '{:.2f}'},
                 'PTC/PTCPot': {'etiq': '% Puntos Pot',
                                'leyenda': '% Puntos si hubiese entrado todo',
                                'formato': '{:.2f}%'},
                 'R-D': {'etiq': 'Reb Def', 'leyenda': 'Rebotes defensivos', 'formato': '{:.2f}'},
                 'R-O': {'etiq': 'Reb Of', 'leyenda': 'Rebotes ofensivos', 'formato': '{:.2f}'},
                 'REB-T': {'etiq': 'Reb total', 'leyenda': 'Rebotes totales', 'formato': '{:.2f}'},
                 'RO/TC-F': {'etiq': 'RO/TC-F', 'leyenda': 'RO/TC-F', 'formato': '{:.2f}'},
                 'Segs': {'etiq': 'Segs', 'leyenda': 'Segs', 'formato': '{:.2f}'},
                 'T1%': {'etiq': 'T1%', 'leyenda': 'T1%', 'formato': '{:.2f}'},
                 'T1-C': {'etiq': 'T1-C', 'leyenda': 'T1-C', 'formato': '{:.2f}'},
                 'T1-I': {'etiq': 'T1-I', 'leyenda': 'T1-I', 'formato': '{:.2f}'},
                 'T2%': {'etiq': 'T2%', 'leyenda': 'T2%', 'formato': '{:.2f}'},
                 'T2-C': {'etiq': 'T2-C', 'leyenda': 'T2-C', 'formato': '{:.2f}'},
                 'T2-I': {'etiq': 'T2-I', 'leyenda': 'T2-I', 'formato': '{:.2f}'},
                 't2/tc-C': {'etiq': 't2/tc-C', 'leyenda': 't2/tc-C', 'formato': '{:.2f}'},
                 't2/tc-I': {'etiq': 't2/tc-I', 'leyenda': 't2/tc-I', 'formato': '{:.2f}'},
                 'T3%': {'etiq': 'T3%', 'leyenda': 'T3%', 'formato': '{:.2f}'},
                 'T3-C': {'etiq': 'T3-C', 'leyenda': 'T3-C', 'formato': '{:.2f}'},
                 'T3-I': {'etiq': 'T3-I', 'leyenda': 'T3-I', 'formato': '{:.2f}'},
                 't3/tc-C': {'etiq': 't3/tc-C', 'leyenda': 't3/tc-C', 'formato': '{:.2f}'},
                 't3/tc-I': {'etiq': 't3/tc-I', 'leyenda': 't3/tc-I', 'formato': '{:.2f}'},
                 'TAP-C': {'etiq': 'TAP-C', 'leyenda': 'TAP-C', 'formato': '{:.2f}'},
                 'TAP-F': {'etiq': 'TAP-F', 'leyenda': 'TAP-F', 'formato': '{:.2f}'},
                 'TC%': {'etiq': 'TC%', 'leyenda': 'TC%', 'formato': '{:.2f}'},
                 'TC-C': {'etiq': 'TC-C', 'leyenda': 'TC-C', 'formato': '{:.2f}'},
                 'TC-I': {'etiq': 'TC-I', 'leyenda': 'TC-I', 'formato': '{:.2f}'},
                 'utilizados': {'etiq': 'utilizados',
                                'leyenda': 'utilizados',
                                'formato': '{:.2f}'},
                 'V': {'etiq': 'V', 'leyenda': 'V', 'formato': '{:.2f}'}}


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
                'valJornada': "v_%05.2f",
                'broker': "b_%010d"}
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

from collections import namedtuple

from CAPcore.Misc import BadParameters

URL_BASE = "http://www.acb.com"

bool2esp = {True: "S", False: "N"}
haGanado2esp = {True: "V", False: "D"}
titular2esp = {True: "T", False: "B"}
local2esp = {True: "L", False: "V"}
local2espLargo = {True: "Local", False: "Visitante"}

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
RANKFORMAT = '{:2d}'
DEFAULTPERCFORMAT = DEFAULTNUMFORMAT + '%'

REPORTLEYENDAS = {'+/-': {'etiq': '+/-', 'leyenda': 'Cambio en la anotación con él en el campo'},
                  'A': {'etiq': 'A', 'leyenda': 'Asistencias'},
                  'A/BP': {'etiq': 'Asist / Perd', 'leyenda': 'Asistencias dadas por balón perdido'},
                  'A/TC-C': {'etiq': '% Can de As', 'leyenda': ' % Canastas procedente de asistencia',
                             'formato': DEFAULTPERCFORMAT}, 'BP': {'etiq': 'BP', 'leyenda': 'Balones perdidos'},
                  'BR': {'etiq': 'BR', 'leyenda': 'Balones robados'}, 'C': {'etiq': 'C', 'leyenda': 'Contraataques'},
                  'convocados': {'etiq': 'Conv', 'leyenda': 'Jugadores en la convocatoria'},
                  'eff-t1': {'etiq': '% Puntos TL', 'leyenda': '% Puntos de tiro libre', 'formato': DEFAULTPERCFORMAT},
                  'eff-t2': {'etiq': '% Puntos 2', 'leyenda': '% Puntos de canasta de 2', 'formato': DEFAULTPERCFORMAT},
                  'eff-t3': {'etiq': '% Puntos 3', 'leyenda': '% Puntos de canasta de 3', 'formato': DEFAULTPERCFORMAT},
                  'EffRebD': {'etiq': 'Ef reb Def',
                              'leyenda': 'Eficiencia rebote defensivo (% Rebotes defensivos de los posibles)',
                              'formato': DEFAULTPERCFORMAT},
                  'EffRebO': {'etiq': 'Ef reb Of', 'leyenda': 'Eficiencia rebote ofensivo (% Rebotes ofensivos de los '
                                                              'posibles)', 'formato': DEFAULTPERCFORMAT},
                  'FP-C': {'etiq': 'FRec', 'leyenda': 'Faltas recibidas'},
                  'FP-F': {'etiq': 'FCom', 'leyenda': 'Faltas cometias'},
                  'haGanado': {'etiq': 'Victorias', 'leyenda': 'Ratio de victorias'},
                  'local': {'etiq': 'Part en casa', 'leyenda': 'Ratio de partidos en casa'},
                  'M': {'etiq': 'Mates', 'leyenda': 'Mates'},
                  'OER': {'etiq': 'Rating Of', 'leyenda': 'Rating ofensivo (Puntos anotados por posesión)'},
                  'DER': {'etiq': 'Rating Def', 'leyenda': 'Rating defensivo (Puntos recibidos por posesión)'},
                  'OERpot': {'etiq': 'OERpot',
                             'leyenda': 'Rating ofensivo potencial (Puntos anotados por posesión si no hubiese '
                                        'pérdidas)'},
                  'DERpot': {'etiq': 'DERpot', 'leyenda': 'Rating defensivo potencial (Puntos '
                                                          'recibidos por posesión si '
                                                          'no hubiese pérdidas)'},
                  'P': {'etiq': 'P', 'leyenda': 'Puntos anotados'},
                  'Prec': {'etiq': 'P rec', 'leyenda': 'Puntos recibidos'},
                  'PNR': {'etiq': 'BP Prop', 'leyenda': 'Perdidas no robadas ('
                                                        'balones a la grada, '
                                                        'pasos, comerse la '
                                                        'posesión...)'},
                  'POS': {'etiq': 'Pos', 'leyenda': 'Posesiones'},
                  'ppTC': {'etiq': 'Pts cada tiro', 'leyenda': 'Puntos anotados por tiro de campo hecho'},
                  'PTC/PTCPot': {'etiq': '% Pts Pot',
                                 'leyenda': '% Puntos potenciales (Puntos anotados / Puntos si hubiese entrado todo)',
                                 'formato': DEFAULTPERCFORMAT},
                  'R-D': {'etiq': 'Reb Def', 'leyenda': 'Rebotes defensivos'},
                  'R-O': {'etiq': 'Reb Of', 'leyenda': 'Rebotes ofensivos'},
                  'REB-T': {'etiq': 'Reb total', 'leyenda': 'Rebotes totales'},
                  'RO/TC-F': {'etiq': 'RO/TC-F', 'leyenda': 'RO/TC-F'}, 'Segs': {'etiq': 'Segs', 'leyenda': 'Segs'},
                  'T1%': {'etiq': 'T1%', 'leyenda': 'Tiros libres (%)', 'formato': DEFAULTPERCFORMAT},
                  'T1-C': {'etiq': 'T1-C', 'leyenda': 'Tiros libres anotados'},
                  'T1-I': {'etiq': 'T1-I', 'leyenda': 'Tiros libres lanzados'},
                  'T2%': {'etiq': 'T2%', 'leyenda': 'Tiros de 2 (%)', 'formato': DEFAULTPERCFORMAT},
                  'T2-C': {'etiq': 'T2-C', 'leyenda': 'Tiros de 2 anotados'},
                  'T2-I': {'etiq': 'T2-I', 'leyenda': 'Tiros de 2 lanzados'},
                  't2/tc-C': {'etiq': '%Can 2', 'leyenda': 'Canastas de 2 (%)', 'formato': DEFAULTPERCFORMAT},
                  't2/tc-I': {'etiq': '%Tiros 2', 'leyenda': 'Tiros de 2 (%)', 'formato': DEFAULTPERCFORMAT},
                  'T3%': {'etiq': 'T3%', 'leyenda': 'Triples (%)', 'formato': DEFAULTPERCFORMAT},
                  'T3-C': {'etiq': 'T3-C', 'leyenda': 'Triples anotados'},
                  'T3-I': {'etiq': 'T3-I', 'leyenda': 'Triples lanzados'},
                  't3/tc-C': {'etiq': '%Can 3', 'leyenda': 'Canastas de 3 (%)', 'formato': DEFAULTPERCFORMAT},
                  't3/tc-I': {'etiq': '%Tiros 3', 'leyenda': 'Tiros de 3 (%)', 'formato': DEFAULTPERCFORMAT},
                  'TAP-C': {'etiq': 'Tap rec', 'leyenda': 'Tapones recibidos'},
                  'TAP-F': {'etiq': 'Tapones', 'leyenda': 'Tapones hechos'},
                  'TC%': {'etiq': 'TC%', 'leyenda': 'Tiros de campo (%)', 'formato': DEFAULTPERCFORMAT},
                  'TC-C': {'etiq': 'TC-C', 'leyenda': 'Tiros de campo anotados'},
                  'TC-I': {'etiq': 'TC-I', 'leyenda': 'Tiros de campo lanzados'},
                  'utilizados': {'etiq': 'Usados', 'leyenda': 'Jugadores utilizados'},
                  'V': {'etiq': 'V', 'leyenda': 'Valoración ACB'}}


def OtherLoc(team):
    if team == 'Local':
        return 'Visitante'
    if team == 'Visitante':
        return 'Local'

    raise BadParameters(f"OtherLoc: '{team}' provided. It only accept 'Visitante' or 'Local'")


def OtherTeam(team):
    if team == 'Eq':
        return 'Rival'
    if team == 'Rival':
        return 'Eq'

    raise BadParameters(f"OtherTeam: '{team}' provided. It only accept 'Eq' or 'Rival'")


infoSigPartido = namedtuple(typename='infoSigPartido',
                            field_names=['sigPartido', 'abrevLV', 'jugLocal', 'pendLocal', 'jugVis', 'pendVis',
                                         'eqIsLocal'], defaults=[None, None, None, None, None, None, None, ])
infoClasifEquipo = namedtuple('infoClasifEquipo',
                              ['Jug', 'V', 'D', 'Pfav', 'Pcon', 'Lfav', 'Lcon', 'Jjug', 'CasaFuera', 'idEq',
                               'nombresEq', 'abrevsEq', 'nombreCorto', 'abrevAusar', 'ratioV', 'ratioVent'])
infoClasifBase = namedtuple(typename='infoClasifEquipo', field_names=['Jug', 'V', 'D', 'Pfav', 'Pcon'],
                            defaults=(0, 0, 0, 0, 0))
infoPartLV = namedtuple(typename='infoPartLV', field_names=['Local', 'Visitante'], defaults=[None, None])
infoEqCalendario = namedtuple(typename='infoEqCalendario',
                              field_names=['icono', 'imageTit', 'haGanado', 'abrev', 'nomblargo', 'nombcorto',
                                           'puntos'], defaults=[None, None, None, None, None, None, None])

filaTrayectoriaEq = namedtuple(typename='filaTrayectoriaEq',
                               field_names=['fechaPartido', 'jornada', 'cod_edicion', 'cod_competicion', 'equipoMe',
                                            'equipoRival', 'esLocal', 'haGanado', 'pendiente', 'url', 'abrevEqs',
                                            'resultado'],
                               defaults=[None, None, None, None, None, None, None, None, None, None, None, None])
filaMergeTrayectoria = namedtuple(typename='filaMergeTrayectoria',
                                  field_names=['jornada', 'izda', 'dcha', 'precedente'],
                                  defaults=[None, None, None, None])

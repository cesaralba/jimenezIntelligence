from collections import namedtuple

from CAPcore.Misc import BadParameters

URL_BASE = "https://www.acb.com"

DEFTZ = "CET"

bool2esp = {True: "S", False: "N"}
haGanado2esp = {True: "V", False: "D"}
titular2esp = {True: "T", False: "B"}
local2esp = {True: "L", False: "V"}
local2espLargo = {True: "Local", False: "Visitante"}

LocalVisitante = ('Local', 'Visitante')
EqRival = ('Eq', 'Rival')

LOCALNAMES = {'Local', 'L', 'local'}
VISITNAMES = {'Visitante', 'V', 'visitante'}

POLABELLIST = ['1/8 de final', '1/4 de final', 'semifinales', 'final']
POLABEL2FASE = {'final': 'Final', 'semifinales': 'Semis', '1/4 de final': 'Cuartos', '1/8 de final': 'Octavos'}
POLABEL2ABREV = {'final': 'F', 'semifinales': 'S', '1/4 de final': 'C', '1/8 de final': 'O'}

PLAYOFFFASE = {1: 'Final', 2: 'Semis', 4: 'Cuartos', 8: 'Octavos'}
PLAYOFFABREV = {'Final': 'F', 'Semis': 'S', 'Cuartos': 'C', 'Octavos': 'O'}

DESCENSOS = 2
MARCADORESCLASIF = [2, 4, 8, -DESCENSOS]

# 'FP-C' Faltas recibidas, 'FP-F' Faltas cometidas, 'TAP-C' Tapones recibidos, 'TAP-F' Tapones hechos
ALLCATS = {'+/-', 'A', 'A/BP', 'A/TC-C', 'BP', 'BR', 'C', 'DER', 'DERpot', 'EffRebD', 'EffRebO', 'FP-C', 'FP-F', 'M',
           'OER', 'OERpot', 'P', 'PNR', 'POS', 'POStot', 'PTC/PTCPot', 'Priv', 'Ptot', 'R-D', 'R-O', 'REB-T', 'RO/TC-F',
           'Segs', 'T1%', 'T1-C', 'T1-I', 'T2%', 'T2-C', 'T2-I', 'T3%', 'T3-C', 'T3-I', 'TAP-C', 'TAP-F', 'TC%', 'TC-C',
           'TC-I', 'V', 'Vict', 'convocados', 'eff-t2', 'eff-t3', 'haGanado', 'local', 'ppTC', 't2/tc-C', 't2/tc-I',
           't3/tc-C', 't3/tc-I', 'utilizados'}

DEFAULTNUMFORMAT = '{:3.2f}'
RANKFORMAT = '{:2d}'
DEFAULTPERCFORMAT = DEFAULTNUMFORMAT + '%'

REGEX_JLR = r'Jornada\s*(?P<jornada>\d+)'
REGEX_PLAYOFF = r'(?P<etiqFasePOff>.+)\s+\((?P<numPartPoff>\d+).\)\s*'


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


infoJornada = namedtuple('infoJornada', field_names=['jornada', 'esPlayOff', 'fasePlayOff', 'partRonda'],
                         defaults=[False, None, None])

infoSigPartido = namedtuple(typename='infoSigPartido',
                            field_names=['sigPartido', 'abrevLV', 'jugLocal', 'pendLocal', 'jugVis', 'pendVis',
                                         'eqIsLocal'], defaults=[None, None, None, None, None, None, None, ])

infoPartLV = namedtuple(typename='infoPartLV', field_names=['Local', 'Visitante'], defaults=[None, None])
infoEqCalendario = namedtuple(typename='infoEqCalendario',
                              field_names=['icono', 'imageTit', 'haGanado', 'abrev', 'nomblargo', 'nombcorto',
                                           'puntos'], defaults=[None, None, None, None, None, None, None])

filaTrayectoriaEq = namedtuple(typename='filaTrayectoriaEq',
                               field_names=['fechaPartido', 'jornada', 'cod_edicion', 'cod_competicion', 'equipoMe',
                                            'equipoRival', 'esLocal', 'haGanado', 'pendiente', 'url', 'abrevEqs',
                                            'resultado', 'infoJornada'],
                               defaults=[None, None, None, None, None, None, None, None, None, None, None, None, None])
filaMergeTrayectoria = namedtuple(typename='filaMergeTrayectoria',
                                  field_names=['jornada', 'izda', 'dcha', 'precedente', 'infoJornada', 'pendiente'],
                                  defaults=[None, None, None, None, None, False])
URLIMG2IGNORE = {'/Images/Web/silueta1.gif', '/Images/Web/silueta2.gif', ''}

CLAVESFICHAPERSONA = {'URL', 'audioURL', 'nombre', 'alias', 'lugarNac', 'fechaNac', 'nacionalidad'}
CLAVESFICHAJUGADOR = {'posicion', 'altura', 'licencia', 'junior'}
CLAVESFICHAENTRENADOR = []

CLAVESDICT = ['id', 'URL', 'alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia',
              'primPartidoT', 'ultPartidoT', 'ultPartidoP']
TRADPOSICION = {'Alero': 'A', 'Escolta': 'E', 'Base': 'B', 'Pívot': 'P', 'Ala-pívot': 'AP', '': '?'}
POSABREV2NOMBRE = {'A': 'Alero', 'E': 'Escolta', 'B': 'Base', 'P': 'Pívot', 'AP': 'Ala-pívot'}


def numPartidoPO2jornada(fasePO: str, numPart: str) -> int:
    """
Convierte la ronda/partido entre una jornada numérica. Hecho para no depender de la jornada calculada por ACB
que depende del número de partidos/jornadas
    :param fasePO: cadenas conocidas hasta el momento en la página de ACB
    :param numPart: número de partido en la serie de playoff
    :return: número de jornada (base de la ronda + número de partido en la serie
    """
    fasePO2jorBase: dict[str, int] = {'1/8 de final': 50, '1/4 de final': 60, 'semifinales': 70, 'final': 80,
                                      'octavos de final': 50,
                                      'cuartos de final': 60, 'semifinal': 70}

    return fasePO2jorBase[fasePO.lower()] + int(numPart)

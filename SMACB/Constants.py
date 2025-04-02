from collections import namedtuple
from decimal import Decimal

from CAPcore.Misc import BadParameters

URL_BASE = "https://www.acb.com"

bool2esp = {True: "S", False: "N"}
haGanado2esp = {True: "V", False: "D"}
titular2esp = {True: "T", False: "B"}
local2esp = {True: "L", False: "V"}
local2espLargo = {True: "Local", False: "Visitante"}

LocalVisitante = ('Local', 'Visitante')
EqRival = ('Eq', 'Rival')

LOCALNAMES = {'Local', 'L', 'local'}
VISITNAMES = {'Visitante', 'V', 'visitante'}

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
                              ['Jug', 'V', 'D', 'Pfav', 'Pcon', 'Jjug', 'CasaFuera', 'idEq', 'nombresEq', 'abrevsEq',
                               'nombreCorto', 'abrevAusar', 'ratioVict', 'sumaCoc'])
infoClasifBase = namedtuple(typename='infoClasifEquipo', field_names=['Jug', 'V', 'D', 'Pfav', 'Pcon'],
                            defaults=(0, 0, 0, 0, 0))

infoClasifComplPareja = namedtuple(typename='infoClasifComplPareja',
                                   field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                   defaults=(0, 0, 0, 0, 0, Decimal(0.000)))

infoClasifComplMasD2 = namedtuple(typename='infoClasifComplMasD2',
                                  field_names=['EmpV', 'EmpRatV', 'EmpDifP', 'EmpPfav', 'LRDifP', 'LRPfav', 'LRSumCoc'],
                                  defaults=(0, 0, 0, 0, 0, 0, Decimal(0.000)))

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
URLIMG2IGNORE = {'/Images/Web/silueta1.gif', '/Images/Web/silueta2.gif', ''}
CLAVESFICHAJUGADOR = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia',
                      'junior', 'audioURL']
CLAVESDICT = ['id', 'URL', 'alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia',
              'primPartidoT', 'ultPartidoT', 'ultPartidoP']
TRADPOSICION = {'Alero': 'A', 'Escolta': 'E', 'Base': 'B', 'Pívot': 'P', 'Ala-pívot': 'AP', '': '?'}
POSABREV2NOMBRE = {'A': 'Alero', 'E': 'Escolta', 'B': 'Base', 'P': 'Pívot', 'AP': 'Ala-pívot'}

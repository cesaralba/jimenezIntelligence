from collections import namedtuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Frame, PageTemplate

from SMACB.Constants import DEFAULTPERCFORMAT

CANTGREYEQ = .80
colEq = colors.rgb2cmyk(CANTGREYEQ, CANTGREYEQ, CANTGREYEQ)
estiloPosMarker = [colors.black]
estiloNegBal = [colors.black, "squared", (2, 6)]
DEFTABVALUE = "-"
MARGENFRAME = 2 * mm
frameNormal = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[0] - 2 * MARGENFRAME, height=A4[1] - 2 * MARGENFRAME,
                    leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                    topPadding=MARGENFRAME)
frameApaisado = Frame(x1=MARGENFRAME, y1=MARGENFRAME, width=A4[1] - 2 * MARGENFRAME, height=A4[0] - 2 * MARGENFRAME,
                      leftPadding=MARGENFRAME, bottomPadding=MARGENFRAME, rightPadding=MARGENFRAME,
                      topPadding=MARGENFRAME)
pagNormal = PageTemplate('normal', pagesize=A4, frames=[frameNormal], autoNextPageTemplate='normal')
pagApaisada = PageTemplate('apaisada', pagesize=landscape(A4), frames=[frameApaisado], autoNextPageTemplate='apaisada')
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

# Colores para informe (tabla ligas)
CANTGREYBAL = .70
ANCHOMARCAPOS = 2
colorTablaDiagonal = colors.rgb2cmyk(CANTGREYBAL, CANTGREYBAL, CANTGREYBAL)

nombresClasif = namedtuple('nombresClasif', field_names=('pos', 'abrev', 'nombre'))

criterioDesempateCruces = {'EmpV': {'Leyenda': 'Victorias', 'Clave': ''},
                           'EmpRatV': {'Leyenda': 'Ratio de victorias', 'Clave': 'R'},
                           'EmpDifP': {'Leyenda': 'Average', 'Clave': 'A'},
                           'LRDifP': {'Leyenda': 'Diferencia de puntos (LR)', 'Clave': 'D'},
                           'LRPfav': {'Leyenda': 'Puntos a favor (LR)', 'Clave': 'P'},
                           'LRSumCoc': {'Leyenda': 'Suma de cocientes (LR)', 'Clave': 'C'}, }

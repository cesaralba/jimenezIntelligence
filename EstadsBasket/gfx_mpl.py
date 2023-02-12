import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import DateFormatter

from SMACB.Constants import OtherTeam
from Utils.Misc import listize
from .preparaDatos import teamMatch, calculaEstadisticosPartidos

REQCABS = [('Eq', 'abrev'), ('Rival', 'abrev')]
COLOREQ1 = 'red'
STYLEEQ1 = '--'
COLOREQ2 = 'blue'
STYLEEQ2 = ':'

COLSESTADMEDIAN = ['min', 'max', '50%']
MARKERSTADMEDIAN = '^v*'
COLSESTADAVG = ['min', 'mean', 'max']
MARKERSTAD = '^+v'
COLSESTADBOTH = ['min', 'mean', 'max', '50%']
MARKERSTADBOTH = '^+v*'

DEFAULTCOLOR = 'black'
DEFAULTALPHA = 1.0
DEFAULTLINESTYLE = '-'
DEFAULTMARKER = ''


def dibujaTodo(ax, dfTodo, etiq=('Eq', 'P_por40m'), team1='RMB', team2='LNT'):
    x1 = dfTodo[teamMatch(dfTodo, team1, teamOnly=True)][etiq].index
    y1 = dfTodo[teamMatch(dfTodo, team1, teamOnly=True)][etiq]

    x2 = dfTodo[teamMatch(dfTodo, team2, teamOnly=True)][etiq].index
    y2 = dfTodo[teamMatch(dfTodo, team2, teamOnly=True)][etiq]

    o1 = ax.plot(x1, y1, c='blue', marker='x')
    o2 = ax.plot(x2, y2, c='red', marker='o')

    return o1, o2


def buildLabels(pref, categ, estads):
    if pref == '':
        result = [f"{categ} {val}" for val in estads]
    else:
        result = [f"{pref} {categ} {val}" for val in estads]
    return result


def extendList(lista, listaref, defValue):
    if len(lista) == len(listaref):
        result = lista
    elif len(lista) == 1:
        result = lista * len(listaref)
    else:
        result = [defValue] * (len(listaref) - len(lista))

    return result


def find_filters(dfSorted, abrev1, abrev2):
    """
    Finds the filters (a series of bool that can be used to extract certain rows from a dataframe)
    :param dfSorted: target dataframe
    :param abrev1: abrev of team 1
    :param abrev2: abrev of team 2

    :return: dictionary with all envisioned filters
    """
    result = dict()
    result['games1'] = teamMatch(dfSorted, abrev1, teamOnly=True)
    result['games2'] = teamMatch(dfSorted, abrev2, teamOnly=True)
    result['precs1'] = teamMatch(dfSorted, abrev1) & teamMatch(dfSorted, abrev2) & (dfSorted[('Eq', 'abrev')] == abrev1)
    result['precs2'] = teamMatch(dfSorted, abrev1) & teamMatch(dfSorted, abrev2) & (dfSorted[('Eq', 'abrev')] == abrev2)
    result['games1_noprec'] = result['games1'] ^ result['precs1']
    result['games2_noprec'] = result['games2'] ^ result['precs2']
    result['filt_both'] = result['games1'] | result['games2']

    return result


def plotEstads(ax, dfEstads: pd.DataFrame, categ, estads, target='Eq', prefijo='', color=DEFAULTCOLOR,
               markers=DEFAULTMARKER, alpha: float = DEFAULTALPHA, linestyle=DEFAULTLINESTYLE):
    estads2wrk = listize(estads)
    colnames = [(target, categ, x) for x in estads2wrk]
    labels = buildLabels(prefijo, categ, estads2wrk)
    colors2wrk = extendList(listize(color), estads2wrk, DEFAULTCOLOR)
    alpha2wrk = extendList(listize(alpha), estads2wrk, DEFAULTALPHA)
    linestyle2wrk = extendList(listize(linestyle), estads2wrk, DEFAULTLINESTYLE)
    marker2wrk = extendList([*markers], estads2wrk, DEFAULTMARKER)

    for colX, labelX, colorX, alphaX, lstyleX, markerX in zip(colnames, labels, colors2wrk, alpha2wrk, linestyle2wrk,
                                                              marker2wrk):
        dfEstads[colX].plot(ax=ax, color=colorX, alpha=alphaX, label=labelX, style=lstyleX, marker=markerX)


def plotTrayEquipo(ax, dfEstads: pd.DataFrame, categ, target='Eq', prefijo='', color=DEFAULTCOLOR, marker=DEFAULTMARKER,
                   alpha: float = DEFAULTALPHA, linestyle=DEFAULTLINESTYLE):
    col2show = (target, categ)
    dfEstads[col2show].plot(kind='line', c=color, ls=linestyle, label=prefijo, ax=ax, marker=marker, alpha=alpha)


def plotAntecedentes(ax: plt.Axes, dfEstads: pd.DataFrame, color=DEFAULTCOLOR, linestyle=DEFAULTLINESTYLE):
    ax.vlines(x=dfEstads.index.to_list(), ymin=ax.get_ylim()[0], ymax=ax.get_ylim()[1], colors=color,
              linestyles=linestyle)


def plotRestOfGames(ax: plt.Axes, dfEstads: pd.DataFrame, categ, target='Eq', color=DEFAULTCOLOR, marker=DEFAULTMARKER,
                    alpha: float = DEFAULTALPHA):
    targetCol = (target, categ)
    ax.scatter(x=dfEstads.index.to_list(), y=dfEstads[[targetCol]], alpha=alpha, c=color, marker=marker)


def dibujaCategoria(dfPartidos, abrev1, abrev2, categ, target='Eq'):
    dfSorted = dfPartidos.sort_values(by=[('Info', 'fechaHoraPartido'), ('Info', 'jornada'), ('Eq', 'abrev')])
    gameFilters = find_filters(dfSorted, abrev1, abrev2)

    ListaCols = [(target, 'abrev'), (OtherTeam(target), 'abrev'), (target, categ), (OtherTeam(target), categ),
                 (target, 'haGanado')]

    datos_Liga = calculaEstadisticosPartidos(dfSorted[ListaCols], col2calc=categ)
    datos_Eq1 = calculaEstadisticosPartidos(dfSorted[ListaCols][gameFilters['games1']], col2calc=categ)
    datos_Eq2 = calculaEstadisticosPartidos(dfSorted[ListaCols][gameFilters['games2']], col2calc=categ)

    games1 = dfSorted[gameFilters['games1']][ListaCols]
    games2 = dfSorted[gameFilters['games2']][ListaCols]

    fig, ejes = plt.subplots()

    plotEstads(ax=ejes, dfEstads=datos_Liga, estads=COLSESTADAVG, categ=categ, target=target, prefijo='ACB',
               alpha=0.2)
    plotEstads(ax=ejes, dfEstads=datos_Eq1, estads=COLSESTADMEDIAN, categ=categ, target=target, color=COLOREQ1,
               alpha=0.4, markers=MARKERSTADMEDIAN, linestyle=STYLEEQ1)
    plotEstads(ax=ejes, dfEstads=datos_Eq2, estads=COLSESTADMEDIAN, categ=categ, target=target, color=COLOREQ2,
               alpha=0.4, markers=MARKERSTADMEDIAN, linestyle=STYLEEQ2)

    plotTrayEquipo(ax=ejes, dfEstads=games1, target=target, categ=categ, prefijo=abrev1, color=COLOREQ1, marker='o',
                   linestyle=STYLEEQ1)
    plotTrayEquipo(ax=ejes, dfEstads=games2, target=target, categ=categ, prefijo=abrev2, color=COLOREQ2, marker='o',
                   linestyle=STYLEEQ2)

    if gameFilters['precs1'].any():
        plotAntecedentes(ax=ejes, dfEstads=dfSorted[gameFilters['precs1']], color='green')

    plotRestOfGames(ax=ejes, dfEstads=dfSorted[~gameFilters['filt_both']], categ=categ, target=target, color='black',
                    marker='.', alpha=0.1)
    date_form = DateFormatter("%d-%m")
    ejes.xaxis.set_major_formatter(date_form)
    ejes.xaxis.set_label_text('Fecha')
    ejes.yaxis.set_label_text(categ)

    # TODO: Tabla con indicación del partido del equipo
    #TODO: Leyendas
    return fig, ejes

# TODO: Kde de las categorías
# TODO: Scatterplot eff of/def

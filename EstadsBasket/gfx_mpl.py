import matplotlib.pyplot as plt
import pandas as pd

from .preparaDatos import teamMatch, calculaEstadisticosPartidos
from Utils.Misc import listize

REQCABS = [('Eq', 'abrev'), ('Rival', 'abrev')]
COLOREQ1='red'
COLOREQ2='blue'

COLSESTADMEDIAN = ['min', 'max','50%']
MARKERSTADMEDIAN = '^v*'
COLSESTADAVG = ['min', 'mean', 'max']
MARKERSTAD = '^+v'
COLSESTADBOTH = ['min', 'mean', 'max','50%']
MARKERSTADBOTH = '^+v*'


DEFAULTCOLOR = 'black'
DEFAULTALPHA = 1
DEFAULTLINESTYLE = '-'
DEFAULTMARKER = ''


def scatter_hist(x, y, ax, ax_histx, ax_histy, binwidth=None):
    # no labels
    ax_histx.tick_params(axis="x", labelbottom=False)
    ax_histy.tick_params(axis="y", labelleft=False)

    # the scatter plot:
    ax.scatter(x, y)

    # now determine nice limits by hand:

    ax_histx.hist(x, )
    ax_histy.hist(y, orientation='horizontal')




def dibujaTodo(ax, dfTodo, etiq=('Eq', 'P_por40m'), team1='RMB', team2='LNT'):
    x1 = dfTodo[teamMatch(dfTodo, team1, teamOnly=True)][etiq].index
    y1 = dfTodo[teamMatch(dfTodo, team1, teamOnly=True)][etiq]

    x2 = dfTodo[teamMatch(dfTodo, team2, teamOnly=True)][etiq].index
    y2 = dfTodo[teamMatch(dfTodo, team2, teamOnly=True)][etiq]

    o1 = ax.plot(x1, y1, c='blue', marker='x')
    o2 = ax.plot(x2, y2, c='red', marker='o')

    return o1, o2

def extendList(lista,listaref,defValue):
    if len(lista) == len(listaref):
        result=lista
    elif len(lista)==1:
        result= lista * len(listaref)
    else:
        result = [defValue] * (len(listaref) - len(lista))

    return result

def buildLabels(pref,categ,estads):
    if pref == '':
        result = [f"{categ} {val}" for val in estads]
    else:
        result = [f"{pref} {categ} {val}" for val in estads]
    return result

def plotEstads(ax, dfEstads: pd.DataFrame, categ, estads, target = 'Eq', prefijo = '', color='black', markers='', alpha=1, linestyle='-'):
    estads2wrk = listize(estads)
    colnames =[(target,categ, x) for x in estads2wrk]
    labels = buildLabels(prefijo,categ,estads2wrk)
    colors2wrk = extendList(listize(color),estads2wrk,DEFAULTCOLOR)
    alpha2wrk = extendList(listize(alpha),estads2wrk,DEFAULTALPHA)
    linestyle2wrk = extendList(listize(linestyle), estads2wrk, DEFAULTLINESTYLE)
    marker2wrk = extendList([*markers],estads2wrk,DEFAULTMARKER)

    for colX,labelX,colorX,alphaX,lstyleX,markerX in zip(colnames,labels,colors2wrk,alpha2wrk,linestyle2wrk,marker2wrk):
        dfEstads[colX].plot(ax=ax,color=colorX,alpha=alphaX,label=labelX,style=lstyleX,marker=markerX)





def dibujaCategoria(dfPartidos, abrev1, abrev2, categ):
    ESTADS2SHOW = ['min','mean','max']
    MARKERS = []
    dfSorted = dfPartidos.sort_index()
    filt1 = teamMatch(dfSorted, abrev1, teamOnly=True)
    filt2 = teamMatch(dfSorted, abrev2, teamOnly=True)

    precs = filt1 & filt2
    filt1_noprec = filt1 ^ precs
    filt2_noprec = filt2 ^ precs
    filt_ambos = filt1 | filt2

    ListaCols = [('Eq', 'abrev'), ('Rival', 'abrev'), ('Eq', categ), ('Rival', categ)]

    datos_Liga = calculaEstadisticosPartidos(dfPartidos[ListaCols], col2calc=categ)
    datos_Eq1 = calculaEstadisticosPartidos(dfPartidos[ListaCols][filt1], col2calc=categ)
    datos_Eq2 = calculaEstadisticosPartidos(dfPartidos[ListaCols][filt2], col2calc=categ)

    parts1 = dfPartidos[filt1][ListaCols]
    parts2 = dfPartidos[filt2][ListaCols]

    fig, ejes = plt.subplots()

    g1=plotEstads(ax=ejes,dfEstads=datos_Liga,estads=COLSESTADAVG,categ=categ,prefijo='ACB',alpha=0.2)
    g2=plotEstads(ax=ejes,dfEstads=datos_Eq1,estads=COLSESTADMEDIAN,categ=categ,color=COLOREQ1,alpha=0.4,markers=MARKERSTADMEDIAN,linestyle='--')
    g3=plotEstads(ax=ejes,dfEstads=datos_Eq2,estads=COLSESTADMEDIAN,categ=categ,color=COLOREQ2,alpha=0.4,markers=MARKERSTADMEDIAN,linestyle=':')

    return g1, g2, g3
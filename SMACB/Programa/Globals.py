from collections import defaultdict
from typing import Optional

import pandas as pd

from SMACB.TemporadaACB import calculaEstadsYOrdenLiga, TemporadaACB
from .Constantes import ESTADISTICOEQ

CATESTADSEQ2IGNORE = {'+/-', 'C', 'convocados', 'haGanado', 'local', 'M', 'Segs', 'utilizados', 'V'}
CATESTADSEQASCENDING = {'DER', 'DERpot', 'Prec', 'BP', 'FP-F', 'TAP-C', 'PNR'}

estadGlobales: Optional[pd.DataFrame] = None
estadGlobalesOrden: Optional[pd.DataFrame] = None
allMagnsInEstads: Optional[set] = None
clasifLiga: Optional[list] = None
numEqs: Optional[int] = None
mitadEqs: Optional[int] = None
tradEquipos: Optional[dict] = {'a2n': defaultdict(str), 'n2a': defaultdict(str), 'i2a': defaultdict(str)}


def recuperaEstadsGlobales(tempData:TemporadaACB):
    global estadGlobales
    global estadGlobalesOrden
    global allMagnsInEstads
    if estadGlobales is None:
        estadGlobales, estadGlobalesOrden = calculaEstadsYOrdenLiga(tempData, estadObj=ESTADISTICOEQ,
                                                                    catsAscending=CATESTADSEQASCENDING,
                                                                    cats2ignore=CATESTADSEQ2IGNORE)
        allMagnsInEstads = {magn for _, magn, _ in estadGlobales.columns}


def recuperaClasifLiga(tempData: TemporadaACB, fecha=None):
    global clasifLiga
    global numEqs
    global mitadEqs

    if clasifLiga is None:
        clasifLiga = tempData.clasifLiga(fecha)
        numEqs = len(clasifLiga)
        mitadEqs = numEqs // 2

        for eq in clasifLiga:
            tradEquipos['a2n'][eq.abrevAusar] = eq.nombreCorto
            tradEquipos['n2a'][eq.nombreCorto] = eq.abrevAusar
            tradEquipos['i2a'][list(eq.idEq)[0]] = eq.abrevAusar

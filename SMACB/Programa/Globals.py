from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

from SMACB.Programa.Clasif import calculaClasifLigaLR, calculaEstadoLigaPO, infoClasifEquipoLR, infoEquipoPO
from SMACB.Programa.Constantes import ESTADISTICOEQ
from SMACB.Programa.FuncionesAux import calculaEstadsYOrdenLiga
from SMACB.TemporadaACB import TemporadaACB

CATESTADSEQ2IGNORE = {'+/-', 'C', 'convocados', 'haGanado', 'local', 'M', 'Segs', 'utilizados', 'V'}
CATESTADSEQASCENDING = {'DER', 'DERpot', 'Prec', 'BP', 'FP-F', 'TAP-C', 'PNR'}

estadGlobales: Optional[pd.DataFrame] = None
estadGlobalesOrden: Optional[pd.DataFrame] = None
allMagnsInEstads: Optional[set] = None
clasifLigaLR: Optional[List[infoClasifEquipoLR]] = None
estadoLigaPO: Optional[Dict[str, infoEquipoPO]] = None

numEqs: Optional[int] = None
mitadEqs: Optional[int] = None
tradEquipos: Optional[dict] = {'a2n': defaultdict(str), 'n2a': defaultdict(str), 'i2a': defaultdict(str)}


def recuperaEstadsGlobales(tempData: TemporadaACB):
    # pylint: disable=global-statement
    global estadGlobales
    global estadGlobalesOrden
    global allMagnsInEstads
    # pylint: enable=global-statement

    if estadGlobales is None:
        estadGlobales, estadGlobalesOrden = calculaEstadsYOrdenLiga(tempData, estadObj=ESTADISTICOEQ,
                                                                    catsAscending=CATESTADSEQASCENDING,
                                                                    cats2ignore=CATESTADSEQ2IGNORE)
        allMagnsInEstads = {magn for _, magn, _ in estadGlobales.columns}


def recuperaClasifLigaLR(tempData: TemporadaACB, fecha=None):
    # pylint: disable=global-statement
    global clasifLigaLR
    global numEqs
    global mitadEqs
    # pylint: enable=global-statement

    if clasifLigaLR is None:
        clasifLigaLR = calculaClasifLigaLR(tempData, fecha)
        numEqs = len(clasifLigaLR)
        mitadEqs = numEqs // 2

        for eq in clasifLigaLR:
            tradEquipos['a2n'][eq.abrevAusar] = eq.nombreCorto
            tradEquipos['n2a'][eq.nombreCorto] = eq.abrevAusar
            tradEquipos['i2a'][list(eq.idEq)[0]] = eq.abrevAusar


def recuperaEstadoLigaPO(tempData: TemporadaACB, fecha=None):
    # pylint: disable=global-statement
    global estadoLigaPO
    # pylint: enable=global-statement

    if estadoLigaPO is None:
        estadoLigaPO = calculaEstadoLigaPO(tempData, fecha)


def clasifLiga2dict(tempData: TemporadaACB, fecha=None) -> Dict[str, infoClasifEquipoLR]:
    recuperaClasifLigaLR(tempData=tempData, fecha=fecha)
    result = {eq.abrevAusar: eq for eq in clasifLigaLR}

    return result

from typing import Dict, Any, Optional

from CAPcore.Misc import copyDictWithTranslation

from SMACB.Constants import CLUBTRADUCCS, CLUBEXCLUDES
from Utils.ProcesaMDACB import extraeDatosRelevantesMD


def extraeDatosEqsDePortadaMD(embData: Dict[str, Any], enlacesEqs: Optional[Dict[str, str]] = None):
    result = {}

    if enlacesEqs is None:
        enlacesEqs = {}

    dataTeams = extraeDatosRelevantesMD(embData=embData, claveDeInteres='teams')

    teamData: Dict[str, Any]
    for teamData in dataTeams.get('teams', []):
        infoClub = {}
        dataLatest = teamData['latest']
        idEq = str(dataLatest['clubId'])
        if idEq in enlacesEqs:
            infoClub['url'] = enlacesEqs[idEq]
        infoClub.update(copyDictWithTranslation(source=dataLatest, translation=CLUBTRADUCCS, excludes=CLUBEXCLUDES))
        result[idEq] = infoClub

    return result

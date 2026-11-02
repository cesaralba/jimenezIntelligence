from pprint import pformat
from typing import Dict, Any, Set

from CAPcore.Misc import copyDictWithTranslation

from SMACB.Constants import TRADPOSICION
from Utils.ProcesaMDACB import extraeDatosRelevantesMD
from Utils.Web import sentinel


def procesaMDplantRaizClubData(rawData: dict) -> Dict[str, Any]:
    result = {}

    auxData = extraeDatosRelevantesMD(rawData, claveDeInteres='clubData')
    clubData = auxData['clubData']

    clubInfo = copyDictWithTranslation(clubData['club'],
                                       excludes={'team', 'stadiumPhotoUrl', 'stadiumAddress', 'contactPhone',
                                                 'contactEmail', 'rosterPhotoUrl', 'webUrl', 'ticketingUrl',
                                                 'merchanUrl', 'instagramUrl', 'twitterUrl', 'facebookUrl',
                                                 'youtubeUrl', 'tikTokUrl', 'validated', 'contrastRequired'})
    result.update(clubInfo)
    teamInfo = copyDictWithTranslation(clubData['club']['team'],
                                       excludes=['id', 'clubId', 'competitionId', 'editionId', 'primaryColorHex',
                                                 'textColorHex', 'logoAlt',
                                                 'secondaryLogo', 'displayColor', 'displayTextColor'])
    teamInfo['clubId'] = str(clubData['club']['team']['clubId'])
    result.update(teamInfo)

    result['estanciaACB'] = extractAvFiltersPlantillaPortada(clubData)

    return result


def procesaMDplantJugs(rawData: Dict[str, Any], dataURLs: Dict[str, str] = sentinel) -> Dict[str, Dict[str, Any]]:
    if dataURLs is sentinel:
        dataURLs = {}
    result = {'jugadores': {}, 'tecnicos': {}}

    if not rawData:
        return result

    auxDataRoster = extraeDatosRelevantesMD(rawData, claveDeInteres='currentRoster')

    if auxDataRoster is None:
        raise ValueError(f"procesaMDplantJugs: incapaz de encontrar datos\n{pformat(rawData)}")

    exclBase = {'age', 'coach', 'isLicenseActive', 'player'}
    tradsBase = {'nationalityCountry': 'nacionalidad', 'height': 'altura', 'licensing': 'licencia'}
    exclSubReg = {'editionId', 'firstName', 'fullBodyImageNoBackgroundUrl', 'fullBodyImageUrl', 'headshotImageAlt',
                  'headshotImageNoBackgroundUrl', 'isLicenseActive', 'lastName', 'nickname', 'nicknameFirstName',
                  'nicknameLastName', 'gameRole'}
    tradsSubReg = {'shirtNumber': 'dorsal', 'nickname': 'nombre', 'firstInitialAndLastName': 'alias',
                   'headshotImageUrl': 'urlFoto'}

    for clave, listaPers in auxDataRoster['currentRoster'].items():
        esJugador = 'player' in clave
        esTecnico = 'staff' in clave
        esActivo = 'Absences' not in clave
        claveInterna, destClave = ('player', 'jugadores') if esJugador else ('coach', 'tecnicos')

        for numOrd, pers in enumerate(listaPers, start=1):
            regPersona = {}

            regPersona.update(copyDictWithTranslation(pers, excludes=exclBase, translation=tradsBase))
            regPersona.update(copyDictWithTranslation(pers[claveInterna], excludes=exclSubReg, translation=tradsSubReg))
            regPersona['persId'] = str(pers[claveInterna]['id'])
            regPersona['activo'] = esActivo
            regPersona['nombre'] = pers[claveInterna].get('nickname',
                                                          f"{pers[claveInterna]['firstName']} "
                                                          f"{pers[claveInterna]['lastName']}")
            regPersona['nombresConocidos'] = set()
            for claveNom in ['firstInitialAndLastName', 'nickname']:
                if claveNom in pers[claveInterna]:
                    regPersona['nombresConocidos'].add(pers[claveInterna][claveNom])
            regPersona['nombresConocidos'].add(f"{pers[claveInterna]['firstName']} {pers[claveInterna]['lastName']}")
            regPersona['nombresConocidos'].add(
                f"{pers[claveInterna]['nicknameFirstName']} {pers[claveInterna]['nicknameLastName']}")

            regPersona['pos'] = TRADPOSICION.get(pers[claveInterna]['gameRole'], '??') if esJugador else \
                pers[claveInterna]['gameRole']
            if esTecnico and esActivo:
                regPersona['dorsal'] = str(numOrd)
            regPersona['imgsConocidas'] = {pers[claveInterna]['headshotImageUrl'],
                                           pers[claveInterna]['fullBodyImageUrl']}
            regPersona['URL'] = dataURLs.get(regPersona['id'], None)

            result[destClave][regPersona['persId']] = regPersona

    return result


def extractAvFiltersPlantillaPortada(embData: Dict) -> Dict[int, Set[str]]:
    excludeCompos = {'Minicopa Endesa'}

    result: Dict[int, Set[str]] = {}

    avFilters = embData.get('availableFilters', {}).get('competitions', [])
    for compoFilter in avFilters:
        compoName = compoFilter['name']
        if compoName in excludeCompos:
            continue
        for edition in compoFilter['editions']:
            edYear = edition['startYear']
            currFiltro = result.get(edYear, set())
            currFiltro.add(compoName)
            result[edYear] = currFiltro

    return result

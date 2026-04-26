import logging
import re
from collections import defaultdict
from time import gmtime
from typing import Dict, NamedTuple, Optional, List, Any

from CAPcore.DictLoggedDict import DictOfLoggedDict, DictOfLoggedDictDiff
from CAPcore.LoggedDict import LoggedDict, LoggedDictDiff
from CAPcore.Misc import onlySetElement, copyDictWithTranslation
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage
from bs4 import Tag

import SMACB.CalendarioACB as SMACBcal
from Utils.ProcessMDparts import procesaMDplantRaizClubData, procesaMDplantJugs
from Utils.Web import getObjID, prepareDownloading, generaURLACB, generaCompParaURL, extraePagDataScripts, \
    getIDfromEncURL
from .CalendarioACB import getURLparamTemporada
from .Constants import URL_BASE, URLIMG2IGNORE

logger = logging.getLogger()


class CambiosPlantillaTipo(NamedTuple):
    club: LoggedDictDiff
    jugadores: DictOfLoggedDictDiff
    tecnicos: DictOfLoggedDictDiff


class InfoClubPortada(NamedTuple):
    idEq: str
    url: str
    nombre: Optional[str]
    abrev: Optional[str]


CAMBIOSCLUB: Dict[str, CambiosPlantillaTipo] = {}


class PlantillaACB():
    def __init__(self, teamId, **kwargs):
        self.id = teamId
        self.edicion = kwargs.get('edicion', None)
        self.URL = kwargs.get('url', generaURLPlantilla(self, URL_BASE))
        self.timestamp = None

        self.club = LoggedDict()
        self.jugadores = DictOfLoggedDict()
        self.tecnicos = DictOfLoggedDict()

    def descargaYactualizaPlantilla(self, home=None, browser=None, config=None) -> bool:
        """
        Descarga los datos y llama al procedimiento para actualizar
        :param home:
        :param browser:
        :param config:
        :param extraTrads:
        :return:
        """
        result = False
        browser, config = prepareDownloading(browser, config)
        try:
            auxURL = generaURLPlantilla(self, URL_BASE)
            if auxURL != self.URL:
                print(f"[{self.id}] '{self.club['nombreActual']}' {self.edicion} URL cambiada: '{self.URL}' -> '"
                      f"{auxURL}'")
                self.URL = auxURL
                result |= True
            logger.info("descargaYactualizaPlantilla. [%s] '%s' (%s) URL %s", self.id,
                        self.club.get('nombreActual', 'Desconocido'), self.edicion, self.URL)
            data = descargaPlantilla(self.URL, home, browser, config)
        except Exception:
            logging.exception(
                "Something happened updating record of '%s' ", self.club)
            return False

        result |= self.actualizaPlantillaDescargada(data)
        return result

    def actualizaPlantillaDescargada(self, data) -> bool:
        result = False

        currTimestamp = data.get('timestamp', gmtime())

        cambiosAux = {k: getattr(self, k).diff(data.get(k, {}), doUpdate=True) for k in CambiosPlantillaTipo._fields}

        result |= self.club.update(data.get('club', {}), timestamp=currTimestamp)
        result |= self.jugadores.update(data.get('jugadores', {}), timestamp=currTimestamp)
        result |= self.tecnicos.update(data.get('tecnicos', {}), timestamp=currTimestamp)

        if self.edicion is None:
            self.edicion = data['edicion']
            result = True

        if result:
            self.timestamp = currTimestamp
            CAMBIOSCLUB[self.id] = CambiosPlantillaTipo(**cambiosAux)

        return result

    def getValorJugadores(self, clave, default=None):
        return self.jugadores.extractKey(key=clave, default=default)

    def actualizaClasesBase(self):
        keyRenamingFoto = {'URLimg': 'urlFoto'}
        keyRenamingJugs = {'nombre': 'alias'}
        keyRenamingJugs.update(keyRenamingFoto)
        self.tecnicos: DictOfLoggedDict = DictOfLoggedDict.updateRelease(self.tecnicos)
        self.tecnicos.renameKeys(keyMapping=keyRenamingFoto)  # Ya tienen nombre y alias
        self.jugadores: DictOfLoggedDict = DictOfLoggedDict.updateRelease(self.jugadores)
        self.jugadores.renameKeys(keyMapping=keyRenamingJugs)  # Lo que se encuentra en la tabla es el alias

        def getFromSet(auxNombre, idx):
            sortedVals = sorted(auxNombre, key=len)
            result = sortedVals[idx]
            return result

        for v in self.tecnicos.valuesV():
            auxFoto = v.get('urlFoto', None)
            if auxFoto is None or auxFoto in URLIMG2IGNORE:
                v.purge({'urlFoto'})

            auxNombre = v.get('nombre', None)
            auxAlias = v.get('alias', None) or auxNombre
            changes = {}
            if auxNombre is not None and isinstance(auxNombre, set):
                changes.update({'nombre': getFromSet(auxNombre, -1)})
            if auxAlias is not None and isinstance(auxAlias, set):
                changes.update({'alias': getFromSet(auxNombre, 0)})
            v.update(changes)

        for v in self.jugadores.valuesV():
            auxFoto = v.get('urlFoto', None)
            if auxFoto is None or auxFoto in URLIMG2IGNORE:
                v.purge({'urlFoto'})

            auxAlias = v.get('alias', None)
            changes = {}
            if auxAlias is not None and isinstance(auxAlias, set):
                changes.update({'alias': getFromSet(auxAlias, 0)})
            v.update(changes)

        return self

    def nombreClub(self):
        return self.club.get('nombreActual', 'TBD')

    def __str__(self):
        result = (f"{self.nombreClub()} [{self.id}] Year: {self.edicion} "
                  f"Jugadores conocidos: {len(self.jugadores)} Entrenadores conocidos: {len(self.tecnicos)}")
        return result

    __repr__ = __str__


def descargaPlantilla(urlPlantilla, home=None, browser=None, config=None):
    result = {}

    browser, config = prepareDownloading(browser, config)

    try:
        logging.debug("descargaPlantilla: downloading %s", urlPlantilla)
        pagPlant = downloadPage(urlPlantilla, home=home, browser=browser, config=config)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result.update(procesaPlantillaPortadaDescargada(pagPlant))

        linksPlant = sacaLinksPlantillaClub(plantDesc=pagPlant)
        result.update(
            descargaPlantillaJugadores(linksPlant['plantilla'], home=pagPlant.source, browser=browser, config=config))

    except Exception as exc:
        print(f"descargaYparseaURLficha: problemas descargando '{urlPlantilla}': {exc}")
        raise exc

    return result


def descargaPlantillaJugadores(urlPlantillaJugs, home=None, browser=None, config=None):
    result = {}
    browser, config = prepareDownloading(browser, config)

    try:
        logging.debug("descargaPlantillaJugadores: downloading %s", urlPlantillaJugs)
        pagPlantJugs = downloadPage(urlPlantillaJugs, home=home, browser=browser, config=config)

        result.update(procesaPlantillaJugsDescargada(pagPlantJugs))

    except Exception as exc:
        logger.exception("descargaYparseaURLficha: problemas descargando '%s'", urlPlantillaJugs)
        raise exc

    return result


def actualizaConBajas(result: dict, datosBajas: dict) -> dict:
    for claseDato in result:
        for k, datos in datosBajas.get(claseDato, {}).items():
            result[claseDato][k] = datos

    return result


def procesaPlantillaPortadaDescargada(plantDesc: DownloadedPage):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """

    embData = extraePagDataScripts(plantDesc, keyword='clubData')

    result = {'jugadores': {}, 'tecnicos': {}, 'club': extraeDatosClub(embData=embData)}

    return result


def procesaTablaBajas(tablaBajas: Tag) -> dict:
    result = defaultdict(dict)

    for row in tablaBajas.find("tbody").find_all("tr"):
        tds = list(row.find_all("td"))

        data = {}

        link = tds[1].find("a").attrs['href']
        data['URL'] = mergeURL(URL_BASE, link)
        data['id'] = getObjID(link, 'ver')
        data['activo'] = False

        data['dorsal'] = row.find("td", {"class": "dorsal"}).get_text().strip()
        nuevosNombres = {sp.get_text().strip() for sp in row.find("td", {"class": "jugador"}).find_all("span")}
        data['alias'] = onlySetElement(nuevosNombres)
        data['nacionalidad'] = tds[3].get_text().strip()
        posics = {tds[2].find("span").get_text().strip()}

        destClass = 'tecnicos' if "ENT" in posics else 'jugadores'

        if destClass == 'jugadores':
            data['posicion'] = onlySetElement(posics)
            data['licencia'] = tds[4].get_text().strip()

        result[destClass][data['id']] = data

    return result


def extraeDatosClub(embData: Dict[str, Any]):
    aux = procesaMDplantRaizClubData(rawData=embData)
    transMDclub = {'stadiumName': 'pabellon', 'stadiumCapacity': 'aforo', 'presidentName': 'presidente',
                   'foundationYear': 'fundacion', 'fullName': 'nombreOficial', 'shortName': 'nombreActual'}
    exclMDclub = {'abbreviatedName', 'logo', 'clubId', 'estanciaACB', 'shirtTextColor'}
    result = copyDictWithTranslation(aux, translation=transMDclub, excludes=exclMDclub)

    return result


def encuentraUltEdicion(plantDesc: DownloadedPage):
    """
    Obtiene la última edición de la temporada del contenido de la página (lo extrae del selector de temporadas)
    :param plantDesc:
    :return:
    """
    fichaData = plantDesc.data

    result = fichaData.find("input", {"name": "select_temporada_id"}).attrs['value']

    return result


def descargaPlantillasCabecera(browser=None, config=None, edicion=None, listaIDs=None) -> List[InfoClubPortada]:
    """
    Descarga los contenidos de las plantillas y los procesa. Servirá para alimentar las plantillas de TemporadaACB
    :param browser:
    :param config:
    :param edicion:
    :param listaIDs: IDs to be considered
    :return:
    """
    browser, config = prepareDownloading(browser, config)

    if listaIDs is None:
        listaIDs = []

    result = []

    urlClubes = generaURLClubesPortada(edicion, URL_BASE)
    paginaRaiz = downloadPage(dest=urlClubes, browser=browser, config=config)

    if paginaRaiz is None:
        raise ConnectionError(f"Incapaz de descargar {urlClubes}")

    raizData = paginaRaiz.data
    # SectionTeams-module-scss-module__7n2dDW__sectionTeams
    rePortDivMain = re.compile(r'SectionTeams-module-scss-module__.*__sectionTeams')
    reInfoClub = re.compile(r'TeamCard-module-scss-module__.*__teamCard__info')
    divLogos: Tag = None
    for ent in raizData.find_all('div', {'class': rePortDivMain}):
        if ent.find('a'):
            divLogos = ent

    if divLogos is None:
        raise ValueError(f"Incapaz de encontrar equipos en '{urlClubes}'")

    for artLink in divLogos.find_all('a'):
        urlLink = artLink['href']
        urlFull = mergeURL(urlClubes, urlLink)
        idEq = getIDfromEncURL(objURL=urlFull)

        if listaIDs and idEq not in listaIDs:
            continue

        infoClub = artLink.find('div', {'class': reInfoClub})
        nombreClub = infoClub.find('h3').get_text() if infoClub else None
        abrevClub = infoClub.find('p').get_text() if infoClub else None

        entradaAux = InfoClubPortada(idEq=idEq, url=urlFull, nombre=nombreClub, abrev=abrevClub)

        result.append(entradaAux)

    return result


def idPlantillasCabecera():
    if SMACBcal.embeddedDataEquipos is None:
        raise ValueError('SMACB.CalendarioACB.embeddedDataEquipos no disponible')

    result = set(SMACBcal.embeddedDataEquipos['eqData'].keys())
    return result


def generaURLPlantilla(plantilla: PlantillaACB, urlRef: Optional[str] = None):
    # https://www.acb.com/es/liga/equipos/baxi-manresa-10?editionId=87
    if urlRef is None:
        urlRef = SMACBcal.calendario_URLBASE

    urlPathItems = ['', 'es', 'liga', 'equipos']
    infoEquipo = generaCompParaURL(nombreEnt=plantilla.club['nombreActual'], idEnt=plantilla.id)
    urlPathItems.append(infoEquipo)
    urlParamsEdic = getURLparamTemporada(plantilla.edicion)

    result = generaURLACB(urlComps=urlPathItems, urlRef=urlRef, urlParams=urlParamsEdic)

    return result


def generaURLClubesPortada(edicion: Optional[str] = None, urlRef: str = None):
    # https://www.acb.com/es/liga/equipos?editionId=88

    if urlRef is None:
        urlRef = SMACBcal.calendario_URLBASE
    urlComps = ['', 'es', 'liga', 'equipos']
    urlParams = getURLparamTemporada(edicion)

    result = generaURLACB(urlComps=urlComps, urlRef=urlRef, urlParams=urlParams)

    return result


def sacaLinksPlantillaClub(plantDesc: DownloadedPage) -> Dict[str, str]:
    result = {}

    reLinksPlant = re.compile(r'HeroSectionTabs-module-scss-module___.*__heroSectionTabs__tab')
    linkSecc: Tag
    for linkSecc in plantDesc.data.find_all('a', {'class': reLinksPlant}):
        href = linkSecc['href']
        label = linkSecc.get_text().lower().strip()
        urlDest = mergeURL(plantDesc.source, href)
        result[label] = urlDest

    return result


def procesaPlantillaJugsDescargada(pagDesc: DownloadedPage):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """

    embData = extraePagDataScripts(pagDesc, keyword='clubInfo')
    linksPersPlant = extraeLinksPersonasPlJug(pagDesc, urlBase=pagDesc.source)
    result = procesaMDplantJugs(embData, dataURLs=linksPersPlant)

    return result


def extraeLinksPersonasPlJug(pag: DownloadedPage, urlBase: str = URL_BASE) -> Dict[str, str]:
    result = {}

    rePlantFotos = re.compile(r'heading--display-3')
    divFotos: Tag = pag.data.find('h2', {'class': rePlantFotos})
    if divFotos is None:
        raise ValueError(f"extraeLinksPersonasPlJug: imposible encontrar enlaces en '{pag.source}'")

    for a in divFotos.parent.parent.find_all('a'):
        destURL = mergeURL(urlBase, a['href'])
        idPers = getIDfromEncURL(destURL)

        result[idPers] = destURL

    return result

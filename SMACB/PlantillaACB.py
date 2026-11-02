import logging
import re
from collections import defaultdict
from copy import copy
from pprint import pp
from typing import Dict, NamedTuple, Optional, List, Any, Set

import bs4
from CAPcore.DataChangeLogger import DataChangesRaw
from CAPcore.DictLoggedDict import DictOfLoggedDict, DictOfLoggedDictDiff
from CAPcore.LoggedClass import LoggedClassGenerator, diffDicts
from CAPcore.LoggedDict import LoggedDict, LoggedDictDiff
from CAPcore.Misc import onlySetElement, getUTC, createDictFromGenerator, copyDictWithTranslation
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage
from bs4 import Tag
from configargparse import Namespace
from mechanicalsoup import StatefulBrowser

import SMACB.CalendarioACB as SMACBcal
from Utils.BoWtraductor import BoWTraductor
from Utils.ProcesaMDACB.Plantilla import procesaMDplantRaizClubData, procesaMDplantJugs
from Utils.ProcesaMDACB.Portada import extraeDatosEqsDePortadaMD
from Utils.Web import getObjID, prepareDownloading, generaURLACB, generaCompParaURL, extraePagDataScripts, \
    getIDfromEncURL
from .CalendarioACB import getURLparamTemporada
from .Constants import URL_BASE, URLIMG2IGNORE, CLUBEXCLUDES, CLUBTRADUCCS, PATHURLJUG, PATHURLEQUIPOS

logger = logging.getLogger()

DataLogger = LoggedClassGenerator(DataChangesRaw)

DATOSPLANTILLADESCARGADOS = {}


class CambiosPlantillaTipo(NamedTuple):
    club: LoggedDictDiff
    jugadores: DictOfLoggedDictDiff
    tecnicos: DictOfLoggedDictDiff


class InfoClubPortada(NamedTuple):
    idEq: str
    url: str
    nombre: Optional[str]
    alias: Optional[str]
    abrev: Optional[str]


CAMBIOSCLUB: Dict[str, Dict] = defaultdict(lambda: {'cambios': set()})


class PlantillaACB(LoggedClassGenerator(DataChangesRaw)):
    def __init__(self, teamId, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        self.clubId: str = teamId
        self.edicion: Optional[str] = None
        self.URL: Optional[str] = None

        self.club: LoggedDict = LoggedDict()
        self.jugadores: DictOfLoggedDict = DictOfLoggedDict()
        self.tecnicos: DictOfLoggedDict = DictOfLoggedDict()

        super().__init__(**kwargs)

        currentValues = self.data2log()

        self.updateDataFields(**kwargs)

        newValues = self.data2log()

        changeInfo = comparaPlantillas(currentValues, newValues)
        if not changeInfo:
            return
        changeInfo['Nuevaficha'] = (None, True)
        self.updateDataLog(changeInfo=changeInfo, timestamp=timestamp)
        CAMBIOSCLUB[self.clubId]['nuevo'] = True
        CAMBIOSCLUB[self.clubId]['cambios'].add(timestamp)

    def actualizaPlantillaDescargada(self, newData) -> bool:
        result = False
        timestamp = newData['timestamp'] = newData.get('timestamp', getUTC())

        currentValues = self.data2log()

        result |= self.updateDataFields(**newData)

        if not result:
            return result

        newValues = self.data2log()
        changeInfo = comparaPlantillas(currentValues, newValues)
        self.updateDataLog(changeInfo=changeInfo, timestamp=timestamp)
        CAMBIOSCLUB[self.clubId]['nuevo'] = True
        CAMBIOSCLUB[self.clubId]['cambios'].add(timestamp)

        return result

    def getValorJugadores(self, clave, default=None):
        return self.jugadores.extractKey(key=clave, default=default)

    def data2log(self) -> dict:
        result = {}
        result.update(self.getCurrentDict(soloActivos=False))
        result.update(self.class2dict(keyList=['edicion', 'URL']))

        return result

    def descargaYactualizaPlantilla(self, browser: Optional[StatefulBrowser] = None,
                                    config: Optional[Namespace | Dict] = None) -> bool:
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
                print(
                    f"[{self.clubId}] '{self.club.get('nombreActual', 'Sin nombre conocido')}' {self.edicion} URL cambiada: '{self.URL}' -> '"
                    f"{auxURL}'")
                self.URL = auxURL
                result |= True
            logger.info("descargaYactualizaPlantilla. [%s] '%s' (%s) URL %s", self.clubId,
                        self.club.get('nombreActual', 'Desconocido'), self.edicion, self.URL)
            data = descargaPlantilla(self.URL, browser, config)
        except Exception:
            logging.exception(
                "Something happened updating record of '%s' ", self.club)
            return False

        result |= self.actualizaPlantillaDescargada(data)
        return result

    # def actualizaPlantillaDescargada(self, data) -> bool:
    #     result = False
    #
    #     currTimestamp = data.get('timestamp', getUTC())
    #
    #     cambiosAux = {k: getattr(self, k).diff(data.get(k, {}), doUpdate=True) for k in CambiosPlantillaTipo._fields}
    #
    #     result |= self.club.update(data.get('club', {}), timestamp=currTimestamp)
    #     result |= self.jugadores.update(data.get('jugadores', {}), timestamp=currTimestamp)
    #     result |= self.tecnicos.update(data.get('tecnicos', {}), timestamp=currTimestamp)
    #
    #     if self.edicion is None:
    #         self.edicion = data['edicion']
    #         result = True
    #
    #     if result:
    #         self.timestamp = currTimestamp
    #         CAMBIOSCLUB[self.clubId] = CambiosPlantillaTipo(**cambiosAux)
    #
    #     return result

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

        def getFromSet(auxNombrePar, idx):
            sortedVals = sorted(auxNombrePar, key=len)
            result = sortedVals[idx]
            return result

        for v in self.tecnicos.valuesV():
            auxFoto = v.get('urlFoto', None)
            if auxFoto in URLIMG2IGNORE.union({None}):
                v.purge({'urlFoto'})

            auxNombre = v.get('nombre', None)
            auxAlias = v.get('alias', None) or auxNombre
            changes = {}
            if auxNombre is not None and isinstance(auxNombre, set):
                changes.update({'nombre': getFromSet(auxNombre, -1)})
            if auxAlias is not None and isinstance(auxAlias, set):
                changes.update({'alias': getFromSet(auxAlias, 0)})
            v.update(changes)

        for v in self.jugadores.valuesV():
            auxFoto = v.get('urlFoto', None)
            if auxFoto in URLIMG2IGNORE.union({None}):
                v.purge({'urlFoto'})

            auxAlias = v.get('alias', None)
            changes = {}
            if auxAlias is not None and isinstance(auxAlias, set):
                changes.update({'alias': getFromSet(auxAlias, 0)})
            v.update(changes)

        return self

    def nombreClub(self):
        return self.club.get('nombreActual', 'TBD')

    def getCurrentDict(self, soloActivos: bool = False):
        """
        Vuelca un dict de dicts con la plantilla
        :param soloActivos:
        :return:
        """
        claves2copy = ['jugadores', 'tecnicos', 'club']
        result = createDictFromGenerator(claves2copy, dict)

        for clave in claves2copy:
            dict2work: dict = getattr(self, clave)

            for idPers, data in dict2work.items():
                if not isinstance(data, dict):
                    result[clave][idPers] = data
                    continue
                if soloActivos and not data['activo']:
                    continue
                auxData = copy(data)
                result[clave][idPers] = auxData

        return result

    def __str__(self):
        result = (f"{self.nombreClub()} [{self.clubId}] Year: {self.edicion} "
                  f"Jugadores conocidos: {len(self.jugadores)} Entrenadores conocidos: {len(self.tecnicos)}")
        return result

    __repr__ = __str__


def descargaPlantilla(urlPlantilla, browser: Optional[StatefulBrowser] = None,
                      config: Optional[Namespace | Dict] = None):
    result = {}

    browser, config = prepareDownloading(browser, config)

    try:
        logging.debug("descargaPlantilla: downloading %s", urlPlantilla)
        pagPlant = downloadPage(urlPlantilla, browser=browser, config=config)
        result['URL'] = browser.get_url()
        result['timestamp'] = getUTC()
        result.update(procesaPlantillaPortadaDescargada(pagPlant))

        linksPlant = sacaLinksPlantillaClub(plantDesc=pagPlant)
        result.update(
            descargaPlantillaJugadores(linksPlant['plantilla'], home=pagPlant.source, browser=browser, config=config))

    except Exception as exc:
        print(f"descargaYparseaURLficha: problemas descargando '{urlPlantilla}': {exc}")
        raise exc

    return result


def descargaPlantillaJugadores(urlPlantillaJugs, home=None, browser: Optional[StatefulBrowser] = None,
                               config: Optional[Namespace | Dict] = None):
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


def procesaTablaBajas(tablaBajas: bs4.Tag) -> dict:
    result = defaultdict(dict)

    for row in tablaBajas.find("tbody").find_all("tr"):
        tds = list(row.find_all("td"))

        data = {}

        link = tds[1].find("a").attrs['href']
        data['URL'] = mergeURL(URL_BASE, link)
        data['id'] = getObjID(link)
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

    result = copyDictWithTranslation(aux, translation=CLUBTRADUCCS, excludes=CLUBEXCLUDES)

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


def descargaPlantillasCabecera_old(browser: Optional[StatefulBrowser] = None, config: Optional[Namespace | Dict] = None,
                                   edicion=None, listaIDs=None) -> List[InfoClubPortada]:
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
            break

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

        entradaAux = InfoClubPortada(idEq=idEq, url=urlFull, nombre=nombreClub, abrev=abrevClub, fullDataEmb={})

        result.append(entradaAux)

    return result


def descargaPlantillasCabecera(browser: Optional[StatefulBrowser] = None, config: Optional[Namespace] = None,
                               edicion: Optional[str] = None,
                               listaIDs: Optional[List[str]] = None) -> List[InfoClubPortada]:
    """
    Descarga los contenidos de las plantillas y los procesa. Servirá para alimentar las plantillas de TemporadaACB
    :param browser:
    :param config:
    :param edicion:
    :param listaIDs: IDs to be considered
    :return:
    """
    global DATOSPLANTILLADESCARGADOS

    browser, config = prepareDownloading(browser, config)

    if listaIDs == []:
        listaIDs = None

    result = []

    if not DATOSPLANTILLADESCARGADOS:
        urlClubes = generaURLClubesPortada(edicion, URL_BASE)
        paginaRaiz = downloadPage(dest=urlClubes, browser=browser, config=config)

        if paginaRaiz is None:
            raise ConnectionError(f"Incapaz de descargar {urlClubes}")

        linksEqsPortada = extraeLinksEqsPortadaEq(pag=paginaRaiz, urlBase=paginaRaiz.source)
        DATOSPLANTILLADESCARGADOS = extraeDatosEqsDePortadaMD(
            embData=extraePagDataScripts(calPage=paginaRaiz, keyword='teams'), enlacesEqs=linksEqsPortada)

    for eq in DATOSPLANTILLADESCARGADOS:

        if listaIDs and eq not in listaIDs:
            continue

        plant2wrk = DATOSPLANTILLADESCARGADOS[eq]

        if 'datosDescargados' not in plant2wrk:
            plant2wrk['datosDescargados'] = descargaPlantilla(plant2wrk['url'], browser=browser, config=config)

            plant2wrk['nom2id'] = {}
            plant2wrk['bow']: Dict[str, BoWTraductor] = {}

            for clavePers in ['tecnicos']:  # CAP: 'jugadores' no incluido porque no es necesario
                plant2wrk['nom2id'][clavePers] = defaultdict(set)
                plant2wrk['bow'][clavePers] = BoWTraductor()

                datosPersEq: Dict[str, Dict[str, Any]] = plant2wrk['datosDescargados'][clavePers]
                for idPers, dataPers in datosPersEq.items():
                    for nom2add in dataPers['nombresConocidos']:
                        plant2wrk['nom2id'][clavePers][nom2add].add(idPers)
                        plant2wrk['bow'][clavePers].addTraduccion(clave=nom2add, valor=idPers)

    for idEq, eqData in DATOSPLANTILLADESCARGADOS.items():
        entradaAux = InfoClubPortada(idEq=idEq, url=eqData['url'], nombre=eqData['nombreActual'],
                                     alias=eqData['nombreOficial'], abrev=eqData['abrev'])

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


    infoEquipo = generaCompParaURL(nombreEnt=plantilla.club['nombreActual'], idEnt=plantilla.clubId)
    urlPathItems = PATHURLEQUIPOS + [infoEquipo]
    urlParamsEdic = getURLparamTemporada(plantilla.edicion)

    result = generaURLACB(urlComps=urlPathItems, urlRef=urlRef, urlParams=urlParamsEdic)

    return result


def generaURLClubesPortada(edicion: Optional[str] = None, urlRef: str = None):
    # https://www.acb.com/es/liga/equipos?editionId=88

    if urlRef is None:
        urlRef = SMACBcal.calendario_URLBASE
    urlComps = PATHURLEQUIPOS
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


def comparaPlantillas(currentData: Dict, newData: Dict) -> Dict:
    result = {}

    clavesDictLD = ['jugadores', 'tecnicos']
    clavesDict = ['club']

    auxValores = diffDicts(copyDictWithTranslation(currentData, excludes=clavesDictLD + clavesDict),
                           copyDictWithTranslation(newData, excludes=clavesDictLD + clavesDict))
    if auxValores:
        result.update({'valores': auxValores})

    for k in clavesDictLD:
        auxDLD = DictOfLoggedDict()
        auxDLD.update(currentData.get(k, {}))
        auxDiff = auxDLD.diff(newData.get(k, {}), doUpdate=True)
        if auxDiff:
            result['dicts'] = result.get('dicts', {})
            result['dicts'].update({k: auxDiff})

    for k in clavesDict:
        auxDLD = LoggedDict()
        auxDLD.update(currentData.get(k, {}))
        auxDiff = auxDLD.diff(newData.get(k, {}), doUpdate=True)
        if auxDiff:
            result['dicts'] = result.get('dicts', {})
            result['dicts'].update({k: auxDiff})

    return result


def InfoClubPortada2ClubDict(data: InfoClubPortada) -> Dict[str, Optional[str]]:
    result = {'nombreActual': data.nombre, 'nombreOficial': data.nombre, 'abrev': data.abrev}

    return result


def extraeLinksEqsPortadaEq(pag: DownloadedPage, urlBase: str = URL_BASE) -> Dict[str, str]:
    """
    Los datos incrustados no incluyen links así que hay que sacarlos haciendo scrapping tradicional
    :param pag:
    :param urlBase:
    :return:
    """
    result = {}

    reListEqs = re.compile(r'SectionTeams-module-scss-module__.*__sectionTeams')
    reLinkClub = re.compile(r'SectionTeams-module-scss-module__.*__sectionTeams__link')

    divEqs: Tag
    linkData: Tag

    for divEqs in pag.data.find_all('div', {'class': reListEqs}):
        for linkData in divEqs.find_all('a', {'class': reLinkClub}):
            urlLink = linkData['href']
            urlFull = mergeURL(urlBase, urlLink)
            idEq = getIDfromEncURL(objURL=urlFull)

            result[idEq] = urlFull

    return result


def nombrePers2idPers(nombre: str, idEq: str, esTecnico: bool = True) -> str | Set[str] | None:
    if not DATOSPLANTILLADESCARGADOS:
        raise ValueError("No se han descargado los datos de las plantillas")
    if idEq not in DATOSPLANTILLADESCARGADOS:
        idsConocidos = ",".join(sorted(DATOSPLANTILLADESCARGADOS.keys()))
        raise ValueError(f"Id de equipo '{idEq}' desconocido. Conocidos: {idsConocidos}")
    claveDeInteres = 'tecnicos' if esTecnico else 'jugadores'
    datosAmirar: Dict[str, str] = DATOSPLANTILLADESCARGADOS[idEq]['nom2id'][claveDeInteres]
    bow: BoWTraductor = DATOSPLANTILLADESCARGADOS[idEq]['bow'][claveDeInteres]

    clavesConocidas = ",".join(sorted(f"'{s}'" for s in datosAmirar.keys()))

    if nombre in datosAmirar:
        return datosAmirar[nombre]

    clave = bow.traduceNombres(nombre, umbral=1)

    if not isinstance(clave, set):
        return clave

    logging.warning("Numero variable de coincidencias para '%s'. Claves encontradas: %s. Claves conocidas: %s", nombre,
                    clave, clavesConocidas)
    return clave


def generaLinkJug(jugPartStr: str, idEq: str) -> str:
    urlRef = DATOSPLANTILLADESCARGADOS[idEq]['url']

    fullPathList = PATHURLJUG + [jugPartStr]

    result = generaURLACB(fullPathList, urlRef)

    return result

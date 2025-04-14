import logging
import sys
import traceback
from collections import defaultdict
from time import gmtime
from typing import Dict, NamedTuple

import bs4
from CAPcore.DictLoggedDict import DictOfLoggedDict, DictOfLoggedDictDiff
from CAPcore.LoggedDict import LoggedDict, LoggedDictDiff
from CAPcore.Misc import onlySetElement
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage

from Utils.ParseoData import extractPlantillaInfoDiv
from Utils.Web import getObjID, generaURLPlantilla, generaURLClubes, prepareDownloading
from .Constants import URL_BASE, URLIMG2IGNORE

logger = logging.getLogger()


class CambiosPlantillaTipo(NamedTuple):
    club: LoggedDictDiff
    jugadores: DictOfLoggedDictDiff
    tecnicos: DictOfLoggedDictDiff


CAMBIOSCLUB: Dict[str, CambiosPlantillaTipo] = {}


class PlantillaACB():
    def __init__(self, teamId, **kwargs):
        self.id = teamId
        self.edicion = kwargs.get('edicion', None)
        self.URL = generaURLPlantilla(self, URL_BASE)
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
            data = descargaURLplantilla(self.URL, home, browser, config)
        except Exception:
            print(
                f"SMACB.PlantillaACB.PlantillaACB.descargaYactualizaPlantilla: something happened updating record of  "
                f"'{self.club}']'", sys.exc_info())
            traceback.print_tb(sys.exc_info()[2])
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


def descargaURLplantilla(urlPlantilla, home=None, browser=None, config=None):
    browser, config = prepareDownloading(browser, config)

    try:
        logging.debug("descargaURLplantilla: downloading %s", urlPlantilla)
        pagPlant = downloadPage(urlPlantilla, home=home, browser=browser, config=config)

        result = procesaPlantillaDescargada(pagPlant)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result['edicion'] = encuentraUltEdicion(pagPlant)
    except Exception as exc:
        print(f"descargaYparseaURLficha: problemas descargando '{urlPlantilla}': {exc}")
        raise exc

    return result


def actualizaConBajas(result: dict, datosBajas: dict) -> dict:
    for claseDato in result:
        for k, datos in datosBajas.get(claseDato, {}).items():
            result[claseDato][k] = datos

    return result


def procesaPlantillaDescargada(plantDesc: DownloadedPage):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """
    class2clave = {'nombre_largo': 'nombre', 'nombre_corto': 'alias'}
    result = {'jugadores': {}, 'tecnicos': {}, 'club': extraeDatosClub(plantDesc)}

    fichaData = plantDesc.data

    cosasUtiles = fichaData.find(name='section', attrs={'class': 'contenido_central_equipo'})

    for bloqueDiv in cosasUtiles.find_all('div', {"class": "grid_plantilla"}):
        for jugArt in bloqueDiv.find_all("article"):
            data = {}

            link = jugArt.find("a").attrs['href']
            data['id'] = getObjID(link, 'ver')

            # Carga con los nombres de una potencial traducción existente
            data['activo'] = True
            if {'caja_jugador_medio_cuerpo', 'caja_jugador_cara'}.intersection(jugArt.attrs['class']):
                destClass = 'jugadores'
                data['pos'] = jugArt.find("div", {"class": "posicion"}).get_text().strip()
                data['alias'] = jugArt.find("div", {"class": "nombre"}).get_text().strip()
            elif {'caja_entrenador_principal', 'caja_entrenador_asistente'}.intersection(jugArt.attrs['class']):
                destClass = 'tecnicos'
                if 'caja_entrenador_principal' in jugArt.attrs['class']:
                    data['alias'] = jugArt.find("div", {"class": "nombre"}).get_text().strip()
                    data['nombre'] = jugArt.find("img").attrs['alt'].strip()
                    data['nombre'] = data['nombre'] or data['alias']
                    data['alias'] = data['alias'] or data['nombre']

                else:
                    # curiosamente los segundos entrenadores tienen los 2 nombres, no así los jugadores
                    for sp in jugArt.find("div", {"class": "nombre"}).find_all("span"):
                        classId = [k for k in sp['class'] if k in class2clave][0]
                        data[class2clave[classId]] = sp.get_text().strip()
            else:
                raise ValueError(f"procesaPlantillaDescargada: no sé cómo tratar entrada: {jugArt}")

            extraData = extractPlantillaInfoDiv(jugArt.find("div", {"class": "info_personal"}), destClass)
            data.update(extraData)

            data['dorsal'] = jugArt.find("div", {"class": "dorsal"}).get_text().strip()

            data['URL'] = mergeURL(URL_BASE, link)
            auxFoto = jugArt.find("img").attrs['src']
            if (auxFoto not in URLIMG2IGNORE) and (auxFoto != ""):
                data['urlFoto'] = mergeURL(URL_BASE, auxFoto)

            result[destClass][data['id']] = data

    tablaBajas = cosasUtiles.find("table", {"class": "plantilla_bajas"})

    if tablaBajas:
        datosBajas = procesaTablaBajas(tablaBajas)
        result = actualizaConBajas(result, datosBajas)

    return result


def procesaTablaBajas(tablaBajas: bs4.element) -> dict:
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


def extraeDatosClub(plantDesc: DownloadedPage):
    result = {}

    fichaData = plantDesc.data

    cosasUtiles = fichaData.find(name='div', attrs={'class': 'datos'})
    result['nombreActual'] = cosasUtiles.find('h1').get_text().strip()
    result['nombreOficial'] = cosasUtiles.find('h3').get_text().strip()

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


def descargaPlantillasCabecera(browser=None, config=None, edicion=None, listaIDs=None):
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

    result = set()

    urlClubes = generaURLClubes(edicion, URL_BASE)
    paginaRaiz = downloadPage(dest=urlClubes, browser=browser, config=config)

    if paginaRaiz is None:
        raise ConnectionError(f"Incapaz de descargar {urlClubes}")

    raizData = paginaRaiz.data
    divLogos = raizData.find('section', {'class': 'contenedora_clubes'})

    for artLink in divLogos.find_all('article'):
        eqLink = artLink.find('div').find('a')
        urlLink = eqLink['href']
        urlFull = mergeURL(browser.get_url(), urlLink)

        idEq = getObjID(objURL=urlFull, clave='id')

        result.add(idEq)

    return result

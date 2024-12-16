import logging
from collections import defaultdict
from time import gmtime

import bs4
from CAPcore.LoggedDict import DictOfLoggedDict, LoggedDict
from CAPcore.Web import downloadPage, mergeURL, DownloadedPage

from Utils.Web import getObjID, generaURLPlantilla, generaURLClubes, prepareDownloading
from .Constants import URL_BASE

logger = logging.getLogger()

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']


class PlantillaACB():
    def __init__(self, teamId, **kwargs):
        self.id = teamId
        self.edicion = kwargs.get('edicion', None)
        self.URL = generaURLPlantilla(self, URL_BASE)
        self.timestamp = None

        self.club = LoggedDict()
        self.jugadores = DictOfLoggedDict()
        self.tecnicos = DictOfLoggedDict()

    def descargaYactualizaPlantilla(self, home=None, browser=None, config=None, extraTrads=None) -> bool:
        """
        Descarga los datos y llama al procedimiento para actualizar
        :param home:
        :param browser:
        :param config:
        :param extraTrads:
        :return:
        """
        browser, config = prepareDownloading(browser, config)

        try:
            data = descargaURLplantilla(self.URL, home, browser, config, otrosNombres=extraTrads)
        except Exception as exc:
            print(
                f"SMACB.PlantillaACB.PlantillaACB.descargaYactualizaPlantilla: something happened updating record of  "
                f"'{self.club}']'", exc)

        return self.actualizaPlantillaDescargada(data)

    def actualizaPlantillaDescargada(self, data) -> bool:
        result = False

        currTimestamp = data.get('timestamp', gmtime())

        result = result | self.club.update(data.get('club', {}), currTimestamp)

        result = result | self.jugadores.update(data.get('jugadores', {}), currTimestamp)
        result = result | self.tecnicos.update(data.get('tecnicos', {}), currTimestamp)

        if self.edicion is None:
            self.edicion = data['edicion']
            result = True

        if result:
            self.timestamp = data.get('timestamp', gmtime())

        return result

    def getValorJugadores(self, clave, default=None):
        return self.jugadores.extractKey(key=clave, default=default)

    def __str__(self):
        result = (f"{self.club.get('nombreActual', 'TBD')} [{self.id}] Year: {self.edicion} "
                  f"Jugadores conocidos: {len(self.jugadores)} Entrenadores conocidos: {len(self.tecnicos)}")
        return result

    __repr__ = __str__


def descargaURLplantilla(urlPlantilla, home=None, browser=None, config=None, otrosNombres=None):
    browser, config = prepareDownloading(browser, config)

    try:
        logging.debug("descargaURLplantilla: downloading %s", urlPlantilla)
        pagPlant = downloadPage(urlPlantilla, home=home, browser=browser, config=config)

        result = procesaPlantillaDescargada(pagPlant, otrosNombres=otrosNombres)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result['edicion'] = encuentraUltEdicion(pagPlant)
    except Exception as exc:
        print(f"descargaURLficha: problemas descargando '{urlPlantilla}': {exc}")
        raise exc

    return result


def actualizaConBajas(result: dict, datosBajas: dict) -> dict:
    for claseDato in result:
        for k, datos in datosBajas.get(claseDato, {}).items():
            result[claseDato][k] = datos

    return result


def procesaPlantillaDescargada(plantDesc: DownloadedPage, otrosNombres: dict = None):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """
    auxTraducciones = otrosNombres or dict()

    result = {'jugadores': dict(), 'tecnicos': dict(), 'club': extraeDatosClub(plantDesc)}

    fichaData = plantDesc.data

    cosasUtiles = fichaData.find(name='section', attrs={'class': 'contenido_central_equipo'})

    for bloqueDiv in cosasUtiles.find_all('div', {"class": "grid_plantilla"}):
        for jugArt in bloqueDiv.find_all("article"):
            data = dict()

            link = jugArt.find("a").attrs['href']
            data['id'] = getObjID(link, 'ver')

            # Carga con los nombres de una potencial traducción existente
            data['nombre'] = set().union(auxTraducciones.get(data['id'], set()))
            data['activo'] = True
            if {'caja_jugador_medio_cuerpo', 'caja_jugador_cara'}.intersection(jugArt.attrs['class']):
                destClass = 'jugadores'
                data['pos'] = jugArt.find("div", {"class": "posicion"}).get_text().strip()
                data['nombre'].add(jugArt.find("div", {"class": "nombre"}).get_text().strip())
            elif {'caja_entrenador_principal', 'caja_entrenador_asistente'}.intersection(jugArt.attrs['class']):
                destClass = 'tecnicos'
                nuevosNombres = set()
                if 'caja_entrenador_principal' in jugArt.attrs['class']:
                    nuevosNombres.add(jugArt.find("div", {"class": "nombre"}).get_text().strip())
                    nuevosNombres.add(jugArt.find("img").attrs['alt'].strip())
                else:
                    nuevosNombres = {sp.get_text().strip() for sp in
                                     jugArt.find("div", {"class": "nombre"}).find_all("span")}
                data['nombre'].update(nuevosNombres)
            else:
                raise ValueError(f"procesaPlantillaDescargada: no sé cómo tratar entrada: {jugArt}")

            data['dorsal'] = jugArt.find("div", {"class": "dorsal"}).get_text().strip()

            data['URL'] = mergeURL(URL_BASE, link)
            data['URLimg'] = jugArt.find("img").attrs['src']

            result[destClass][data['id']] = data

    tablaBajas = cosasUtiles.find("table", {"class": "plantilla_bajas"})

    if tablaBajas:
        datosBajas = procesaTablaBajas(tablaBajas, auxTraducciones)
        result = actualizaConBajas(result, datosBajas)

    return result


def procesaTablaBajas(tablaBajas: bs4.element, traduccionesConocidas: dict) -> dict:
    auxTraducciones = traduccionesConocidas or dict()
    result = defaultdict(dict)

    for row in tablaBajas.find("tbody").find_all("tr"):
        tds = list(row.find_all("td"))

        data = dict()

        link = tds[1].find("a").attrs['href']
        data['URL'] = mergeURL(URL_BASE, link)
        data['id'] = getObjID(link, 'ver')
        data['activo'] = False

        data['nombre'] = set().union(auxTraducciones.get(data['id'], set()))
        data['dorsal'] = row.find("td", {"class": "dorsal"}).get_text().strip()
        nuevosNombres = {sp.get_text().strip() for sp in row.find("td", {"class": "jugador"}).find_all("span")}
        data['nombre'].update(nuevosNombres)

        posics = {tds[2].find("span").get_text().strip()}

        destClass = 'tecnicos' if "ENT" in posics else 'jugadores'
        result[destClass][data['id']] = data

    return result


def extraeDatosClub(plantDesc: DownloadedPage):
    result = dict()

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

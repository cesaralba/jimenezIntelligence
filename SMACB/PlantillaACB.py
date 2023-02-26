import logging
from argparse import Namespace
from collections import defaultdict
from time import gmtime

import bs4

from Utils.LoggedDict import LoggedDict, DictOfLoggedDict
from Utils.Web import creaBrowser, DescargaPagina, getObjID, MergeURL
from .Constants import URL_BASE

logger = logging.getLogger()

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']


class PlantillaACB(object):
    def __init__(self, id, **kwargs):
        self.id = id
        self.edicion = kwargs.get('edicion', None)
        self.URL = generaURLPlantilla(self)
        self.timestamp = None

        self.club = LoggedDict()
        self.jugadores = DictOfLoggedDict()
        self.tecnicos = DictOfLoggedDict()

    def descargaYactualizaPlantilla(self, home=None, browser=None, config=Namespace(), extraTrads=None):
        """
        Descarga los datos y llama al procedimiento para actualizar
        :param home:
        :param browser:
        :param config:
        :param extraTrads:
        :return:
        """
        if browser is None:
            browser = creaBrowser(config)

        data = descargaURLplantilla(self.URL, home, browser, config, otrosNombres=extraTrads)

        return self.actualizaPlantillaDescargada(data)

    def actualizaPlantillaDescargada(self, data):
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
        result = "%s [%s] Year: %s Jugadores conocidos: %i Entrenadores conocidos: %i" % (
            self.club.get('nombreActual', "TBD"), self.id, self.edicion, len(self.jugadores), len(self.tecnicos))
        return result

    __repr__ = __str__

    # def getCode(self, nombre, dorsal=None, esTecnico=False, esJugador=False, umbral=1):
    #
    #     if esJugador:
    #         targetDict = self.jugadores
    #     elif esTecnico:
    #         dorsal = None
    #         targetDict = self.tecnicos
    #     else:  # Ni jugador ni tecnico???
    #         raise ValueError(f"Jugador '{nombre}' ({dorsal or 'Sin dorsal'}) no es ni jugador ni técnico")
    #
    #     resultSet = set()
    #
    #     nombreNormaliz = NormalizaCadena(RetocaNombreJugador(nombre))
    #     setNombre = CreaBoW(nombreNormaliz)
    #
    #     for jCode, jData in targetDict.items():
    #         if dorsal is not None:
    #             if jData['dorsal'] == dorsal:  # Hay dorsal, coincide algo => nos vale
    #                 for jNombre in jData['nombre']:
    #                     dsSet = CreaBoW(NormalizaCadena(RetocaNombreJugador(jNombre)))
    #                     if CompareBagsOfWords(setNombre, dsSet) > 0:
    #                         return jCode
    #         else:  # Sin dorsal no es suficiente sólo con apellidos (apellidos o nombres muy comunes)
    #             for jNombre in jData['nombre']:
    #                 dsSet = CreaBoW(NormalizaCadena(RetocaNombreJugador(jNombre)))
    #                 if CompareBagsOfWords(setNombre, dsSet) > 0:
    #                     resultSet.add(jCode)
    #
    #     if not resultSet:  # Ni siquiera candidatos => nada que hacer
    #         return None
    #     if isinstance(resultSet, set) and len(resultSet) == 1:  # Unica respuesta! => Nos vale
    #         return onlySetElement(resultSet)
    #
    #     # Hay más de una respuesta posible (¿les da miedo citar a Sergio Rodríguez?) Tocará afinar más
    #     codeList = set()
    #     for jCode in resultSet:
    #         jData = targetDict[jCode]
    #         for jNombre in jData['nombre']:
    #             dsNormaliz = NormalizaCadena(RetocaNombreJugador(jNombre))
    #             if comparaNombresPersonas(dsNormaliz, nombreNormaliz, umbral=umbral):
    #                 codeList.add(jCode)
    #
    #     return onlySetElement(codeList)
    #


def descargaURLplantilla(urlPlantilla, home=None, browser=None, config=Namespace(), otrosNombres=None):
    if browser is None:
        browser = creaBrowser(config)
    try:
        logging.debug(f"descargaURLplantilla: downloading {urlPlantilla} ")
        pagPlant = DescargaPagina(urlPlantilla, home=home, browser=browser, config=config)

        result = procesaPlantillaDescargada(pagPlant, otrosNombres=otrosNombres)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result['edicion'] = encuentraUltEdicion(pagPlant)
    except Exception as exc:
        print("descargaURLficha: problemas descargando '%s': %s" % (urlPlantilla, exc))
        raise exc

    return result


def actualizaConBajas(result: dict, datosBajas: dict) -> dict:
    for claseDato in result:
        for k, datos in datosBajas.get(claseDato, {}).items():
            result[claseDato][k] = datos

    return result


def procesaPlantillaDescargada(plantDesc, otrosNombres: dict = None):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """
    auxTraducciones = otrosNombres or dict()

    result = {'jugadores': dict(), 'tecnicos': dict()}

    result['club'] = extraeDatosClub(plantDesc)
    fichaData = plantDesc['data']

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
                raise ValueError("procesaPlantillaDescargada: no sé cómo tratar entrada: %s" % jugArt)

            data['dorsal'] = jugArt.find("div", {"class": "dorsal"}).get_text().strip()

            data['URL'] = MergeURL(URL_BASE, link)
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
        data['URL'] = MergeURL(URL_BASE, link)
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


def extraeDatosClub(plantDesc):
    result = dict()

    fichaData = plantDesc['data']

    cosasUtiles = fichaData.find(name='div', attrs={'class': 'datos'})
    result['nombreActual'] = cosasUtiles.find('h1').get_text().strip()
    result['nombreOficial'] = cosasUtiles.find('h3').get_text().strip()

    return result


def encuentraUltEdicion(plantDesc):
    """
    Obtiene la última edición de la temporada del contenido de la página (lo extrae del selector de temporadas)
    :param plantDesc:
    :return:
    """
    fichaData = plantDesc['data']

    result = fichaData.find("input", {"name": "select_temporada_id"}).attrs['value']

    return result


def descargaPlantillasCabecera(browser=None, config=Namespace(),edicion=None,listaIDs=[]):
    """
    Descarga los contenidos de las plantillas y los procesa. Servirá para alimentar las plantillas de TemporadaACB
    :param browser:
    :param config:
    :param jugId2nombre:
    :return:
    """
    result = dict()
    if browser is None:
        browser = creaBrowser(config)

    urlClubes = generaURLClubes(edicion)
    paginaRaiz = DescargaPagina(dest=urlClubes, browser=browser, config=config)

    if paginaRaiz is None:
        raise ConnectionError("Incapaz de descargar %s" % URL_BASE)

    raizData = paginaRaiz['data']
    divLogos = raizData.find('section', {'class': 'contenedora_clubes'})

    for artLink in divLogos.find_all('article'):
        eqLink = artLink.find('div').find('a')
        urlLink = eqLink['href']
        urlFull = MergeURL(browser.get_url(), urlLink)

        idEq = getObjID(objURL=urlFull, clave='id')

        if listaIDs and idEq not in listaIDs:
            continue

        result[idEq] = descargaURLplantilla(urlFull)

    return result


def generaURLPlantilla(plantilla):
    # http://www.acb.com/club/plantilla/id/6/temporada_id/2016
    params = ['/club', 'plantilla', 'id', plantilla.id]
    if plantilla.edicion is not None:
        params += ['temporada_id', plantilla.edicion]

    urlSTR = "/".join(params)

    result = MergeURL(URL_BASE, urlSTR)

    return result

def generaURLClubes(edicion=None):
    # https://www.acb.com/club/index/temporada_id/2015
    params = ['/club', 'index']
    if edicion is not None:
        params += ['temporada_id', edicion]

    urlSTR = "/".join(params)

    result = MergeURL(URL_BASE, urlSTR)

    return result

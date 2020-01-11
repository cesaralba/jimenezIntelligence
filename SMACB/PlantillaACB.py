from argparse import Namespace
from time import gmtime

from Utils.BoWtraductor import (CompareBagsOfWords, CreaBoW, NormalizaCadena,
                                RetocaNombreJugador, comparaNombresPersonas)
from Utils.Misc import onlySetElement
from Utils.Web import DescargaPagina, MergeURL, creaBrowser, getObjID

from .SMconstants import URL_BASE

CLAVESFICHA = ['alias', 'nombre', 'lugarNac', 'fechaNac', 'posicion', 'altura', 'nacionalidad', 'licencia']


class PlantillaACB(object):
    def __init__(self, id, **kwargs):
        self.id = id
        self.edicion = kwargs.get('edicion', None)
        self.URL = self.generaURL()

        home = kwargs.get('home', None)
        browser = kwargs.get('browser', None)
        config = kwargs.get('config', Namespace())
        extraTrads = kwargs.get('otrosNombres', None)

        data = descargaURLplantilla(self.URL, home, browser, config, otrosNombres=extraTrads)
        self.timestamp = data.get('timestamp', gmtime())

        self.club = data.get('club', {})
        self.jugadores = data.get('jugadores', {})
        self.tecnicos = data.get('tecnicos', {})

        if self.edicion is None:
            self.edicion = data['edicion']

    def generaURL(self):
        # http://www.acb.com/club/plantilla/id/6/temporada_id/2016
        params = ['/club', 'plantilla', 'id', self.id]
        if self.edicion is not None:
            params += ['temporada_id', self.edicion]

        urlSTR = "/".join(params)

        result = MergeURL(URL_BASE, urlSTR)

        return result

    @staticmethod
    def fromURL(urlPlantilla, home=None, browser=None, config=Namespace(), otrosNombres=None):
        if browser is None:
            browser = creaBrowser(config)

        probEd = getObjID(urlPlantilla, 'year', None)
        params = {'id': getObjID(urlPlantilla, 'id'), 'edicion': probEd, 'home': home, 'browser': browser,
                  'config': config, 'otrosNombres': otrosNombres}

        return PlantillaACB(**params)

    def __str__(self):
        result = "%s [%s] Year: %s Jugadores conocidos: %i Entrenadores conocidos: %i" % (
            self.club.get('nombreActual', "TBD"), self.id, self.edicion, len(self.jugadores), len(self.tecnicos))
        return result

    __repr__ = __str__

    def getCode(self, nombre, dorsal=None, esTecnico=False, esJugador=False, umbral=1):

        if esJugador:
            targetDict = self.jugadores
        elif esTecnico:
            dorsal = None
            targetDict = self.tecnicos
        else:  # Ni jugador ni tecnico???
            raise ValueError("Jugador '%s' (%s) no es ni jugador ni técnico" % (
                nombre, dorsal if dorsal is not None else "Sin dorsal"))

        resultSet = set()

        nombreNormaliz = NormalizaCadena(RetocaNombreJugador(nombre))
        setNombre = CreaBoW(nombreNormaliz)

        for jCode, jData in targetDict.items():
            if dorsal is not None:
                if jData['dorsal'] == dorsal:  # Hay dorsal, coincide algo => nos vale
                    for jNombre in jData['nombre']:
                        dsSet = CreaBoW(NormalizaCadena(RetocaNombreJugador(jNombre)))
                        if CompareBagsOfWords(setNombre, dsSet) > 0:
                            return jCode
            else:  # Sin dorsal no es suficiente sólo con apellidos (apellidos o nombres muy comunes)
                for jNombre in jData['nombre']:
                    dsSet = CreaBoW(NormalizaCadena(RetocaNombreJugador(jNombre)))
                    if CompareBagsOfWords(setNombre, dsSet) > 0:
                        resultSet.add(jCode)

        if not resultSet:  # Ni siquiera candidatos => nada que hacer
            return None
        if isinstance(resultSet, set) and len(resultSet) == 1:  # Unica respuesta! => Nos vale
            return onlySetElement(resultSet)

        # Hay más de una respuesta posible (¿les da miedo citar a Sergio Rodríguez?) Tocará afinar más
        codeList = set()
        for jCode in resultSet:
            jData = targetDict[jCode]
            for jNombre in jData['nombre']:
                dsNormaliz = NormalizaCadena(RetocaNombreJugador(jNombre))
                if comparaNombresPersonas(dsNormaliz, nombreNormaliz, umbral=umbral):
                    codeList.add(jCode)

        return onlySetElement(codeList)


def descargaURLplantilla(urlPlantilla, home=None, browser=None, config=Namespace(), otrosNombres=None):
    if browser is None:
        browser = creaBrowser(config)
    try:
        pagPlant = DescargaPagina(urlPlantilla, home=home, browser=browser, config=config)

        result = procesaPlantillaDescargada(pagPlant, otrosNombres=otrosNombres)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result['edicion'] = encuentraUltEdicion(pagPlant)

    except Exception as exc:
        print("descargaURLficha: problemas descargando '%s': %s" % (urlPlantilla, exc))
        raise exc

    return result


def procesaPlantillaDescargada(plantDesc, otrosNombres=None):
    """
    Procesa el contenido de una página de plantilla

    :param plantDesc: bs4 contenido de la página de la plantilla
    :param otrosNombres: diccionario ID->set de nombres
    :return:
    """
    auxTraducciones = otrosNombres if otrosNombres else dict()

    result = dict()

    result['jugadores'] = dict()
    result['tecnicos'] = dict()

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

            if 'caja_jugador_medio_cuerpo' in jugArt.attrs['class'] or 'caja_jugador_cara' in jugArt.attrs['class']:
                destClass = 'jugadores'
                data['pos'] = jugArt.find("div", {"class": "posicion"}).get_text().strip()
                data['nombre'].add(jugArt.find("div", {"class": "nombre"}).get_text().strip())
            elif ('caja_entrenador_principal' in jugArt.attrs['class']) or (
                    'caja_entrenador_asistente' in jugArt.attrs['class']):
                destClass = 'tecnicos'
                if 'caja_entrenador_principal' in jugArt.attrs['class']:
                    data['nombre'].add(jugArt.find("div", {"class": "nombre"}).get_text().strip())
                    data['nombre'].add(jugArt.find("img").attrs['alt'].strip())
                else:
                    for sp in jugArt.find("div", {"class": "nombre"}).find_all("span"):
                        data['nombre'].add(sp.get_text().strip())
            else:
                raise ValueError("procesaPlantillaDescargada: no sé cómo tratar entrada: %s" % jugArt)

            data['dorsal'] = jugArt.find("div", {"class": "dorsal"}).get_text().strip()

            data['URL'] = MergeURL(URL_BASE, link)
            data['URLimg'] = jugArt.find("img").attrs['src']

            result[destClass][data['id']] = data

    tablaBajas = cosasUtiles.find("table", {"class": "plantilla_bajas"})

    if tablaBajas:

        for row in tablaBajas.find("tbody").find_all("tr"):
            tds = list(row.find_all("td"))

            data = dict()

            link = tds[1].find("a").attrs['href']
            data['URL'] = MergeURL(URL_BASE, link)
            data['id'] = getObjID(link, 'ver')

            data['nombre'] = set().union(auxTraducciones.get(data['id'], set()))
            data['dorsal'] = row.find("td", {"class": "dorsal"}).get_text().strip()
            for sp in row.find("td", {"class": "jugador"}).find_all("span"):
                data['nombre'].add(sp.get_text().strip())

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


def descargaPlantillasCabecera(browser=None, config=Namespace(), jugId2nombre=None):
    result = dict()
    if browser is None:
        browser = creaBrowser(config)

    paginaRaiz = DescargaPagina(dest=URL_BASE, browser=browser, config=config)

    if paginaRaiz is None:
        raise Exception("Incapaz de descargar %s" % URL_BASE)

    raizData = paginaRaiz['data']
    divLogos = raizData.find('div', {'class': 'contenedor_logos_equipos'})

    for eqLink in divLogos.find_all('a', {'class': 'equipo_logo'}):
        urlLink = eqLink['href']
        urlFull = MergeURL(browser.get_url(), urlLink)

        idEq = getObjID(objURL=urlFull, clave='id')
        result[idEq] = PlantillaACB.fromURL(urlFull, browser=browser, config=config, otrosNombres=jugId2nombre)

    return result

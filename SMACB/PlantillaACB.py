from argparse import Namespace
from time import gmtime

from Utils.Web import DescargaPagina, creaBrowser, MergeURL, getObjID
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

        self.data = descargaURLplantilla(self.URL, home, browser, config)

        if self.edicion is None:
            self.edicion = self.data['edicion']

        self.timestamp = self.data.get('timestamp', gmtime())

    def generaURL(self):
        # http://www.acb.com/club/plantilla/id/6/temporada_id/2016
        params = ['/club', 'plantilla', 'id', self.id]
        if self.edicion is not None:
            params.append(['temporada_id', self.edicion])

        urlSTR = "/".join(params)

        result = MergeURL(URL_BASE, urlSTR)

        return result

    @staticmethod
    def fromURL(urlPlantilla, home=None, browser=None, config=Namespace()):
        if browser is None:
            browser = creaBrowser(config)

        probEd = getObjID(urlPlantilla, 'year', None)
        params = {'id': getObjID(urlPlantilla, 'id'), 'edicion': probEd, 'home': home, 'browser': browser,
                  'config': config}

        return PlantillaACB(**params)


def descargaURLplantilla(urlPlantilla, home=None, browser=None, config=Namespace()):
    if browser is None:
        browser = creaBrowser(config)
    try:
        pagPlant = DescargaPagina(urlPlantilla, home=home, browser=browser, config=config)

        result = procesaPlantillaDescargada(pagPlant)
        result['URL'] = browser.get_url()
        result['timestamp'] = gmtime()
        result['edicion'] = encuentraUltEdicion(pagPlant)

    except Exception as exc:
        print("descargaURLficha: problemas descargando '%s': %s" % (urlPlantilla, exc))
        raise exc

    return result


def procesaPlantillaDescargada(plantDesc):
    result = dict()

    result['jugadores'] = dict()
    result['tecnicos'] = dict()

    fichaData = plantDesc['data']

    cosasUtiles = fichaData.find(name='section', attrs={'class': 'contenido_central_equipo'})

    for bloqueDiv in cosasUtiles.find_all('div', {"class": "grid_plantilla"}):
        for jugArt in bloqueDiv.find_all("article"):
            data = dict()
            data['nombre'] = set()

            if 'caja_jugador_medio_cuerpo' in jugArt.attrs['class'] or 'caja_jugador_cara' in jugArt.attrs['class']:
                destClass = 'jugadores'
                data['pos'] = jugArt.find("div", {"class": "posicion"}).get_text().strip()
                data['nombre'].add(jugArt.find("div", {"class": "nombre"}).get_text().strip())
            elif 'caja_entrenador_principal' in jugArt.attrs['class'] or 'caja_entrenador_asistente' in jugArt.attrs[
                'class']:
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

            link = jugArt.find("a").attrs['href']
            data['URL'] = MergeURL(URL_BASE, link)
            data['URLimg'] = jugArt.find("img").attrs['src']
            data['id'] = getObjID(link, 'ver')

            result[destClass][data['id']] = data

    tablaBajas = cosasUtiles.find("table", {"class": "plantilla_bajas"})

    if tablaBajas:

        for row in tablaBajas.find("tbody").find_all("tr"):
            tds = list(row.find_all("td"))

            data = dict()
            data['nombre'] = set()
            data['dorsal'] = row.find("td", {"class": "dorsal"}).get_text().strip()
            for sp in row.find("td", {"class": "jugador"}).find_all("span"):
                data['nombre'].add(sp.get_text().strip())

            link = tds[1].find("a").attrs['href']
            data['URL'] = MergeURL(URL_BASE, link)
            data['id'] = getObjID(link, 'ver')

            posics = {tds[2].find("span").get_text().strip()}

            destClass = 'tecnicos' if "ENT" in posics else 'jugadores'
            result[destClass][data['id']] = data

    return result


def encuentraUltEdicion(plantDesc):
    fichaData = plantDesc['data']
    # <input id="select_temporada_id" name="select_temporada_id" type="hidden" value="2019"/><span class="mayusculas" id="select_temporada_titulo"> 
    result = fichaData.find("input", {"name": "select_temporada_id"}).attrs['value']

    return result

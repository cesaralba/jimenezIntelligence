import logging
from typing import Optional

import bs4
from CAPcore.Web import mergeURL, DownloadedPage, downloadPage
from SMACB.Constants import URL_BASE, URLIMG2IGNORE
from Utils.ParseoData import procesaCosasUtilesPlantilla, findLocucionNombre
from Utils.Web import prepareDownloading

VALIDTYPES = {'jugador', 'entrenador'}

class FichaPersona:
    def __init__(self,**kwargs):
        changesInfo = {'NuevoJugador': True}
        self.timestamp = kwargs.get('timestamp', None)

        if 'id' not in kwargs:
            raise ValueError(f"Jugador nuevo sin 'id': {kwargs}")
        self.id = kwargs.get('id', None)
        self.URL = kwargs.get('URL', None)
        self.audioURL = kwargs.get('audioURL', None)
        self.tipoFicha:Optional[str] = None
        self.sinDatos: Optional[bool] = None

        self.nombre = kwargs.get('nombre', None)
        self.alias = kwargs.get('alias', self.nombre)
        self.lugarNac = kwargs.get('lugarNac', None)
        self.fechaNac = kwargs.get('fechaNac', None)
        self.nacionalidad = kwargs.get('nacionalidad', None)

        self.nombresConocidos = set()
        self.urlConocidas = set()
        self.fotos = set()

        self.ultClub = None

        self.primPartidoP = None
        self.ultPartidoP = None
        self.primPartidoT = None
        self.ultPartidoT = None
        self.partidos = set()
        self.equipos = set()

        if self.nombre is not None:
            self.nombresConocidos.add(self.nombre)
        if self.alias is not None:
            self.nombresConocidos.add(self.alias)

        if self.URL is not None:
            self.urlConocidas.add(self.URL)

        self.updateFoto(urlFoto=kwargs.get('urlFoto', None), urlBase=self.URL, changeDict=changesInfo)

        ultClub = kwargs.get('club', None)
        if ultClub is not None:
            self.equipos.add(ultClub)
            self.ultClub = ultClub

    def buildURL(self):
        if self.tipoFicha is None:
            raise ValueError("buildURL: type of data unset")
        if self.tipoFicha not in VALIDTYPES:
            raise ValueError(f"buildURL: unknown type of data. Valid ones: {', '.join(sorted(VALIDTYPES))}")

        newPathList = ['',self.tipoFicha,'temporada-a-temporada','id',self.id]
        newPath = '/'.join(newPathList)

        result = mergeURL(URL_BASE,newPath)

        return result

    def updateFoto(self, urlFoto: Optional[str], urlBase: Optional[str], changeDict: Optional[dict] = None):
        changes = False

        if urlFoto is not None and urlFoto not in URLIMG2IGNORE:
            changes = True
            newURL = mergeURL(urlBase, urlFoto)
            self.fotos.add(newURL)
            if changeDict:
                changeDict['urlFoto'] = ("", "Nueva")
        return changes

def descargaPagina(datos, home=None, browser=None, config=None) -> Optional[DownloadedPage]:
    browser, config = prepareDownloading(browser, config)

    url=datos.buildURL()

    logging.info("Descargando ficha de %s '%s'", datos.tipoFicha, url)
    try:
        result: DownloadedPage = downloadPage(url, home=home, browser=browser, config=config)
    except Exception as exc:
        result = None
        logging.error("Problemas descargando '%s'",url)
        logging.exception(exc)

    return result

def extraeDatosPersonales(datosPag:Optional[DownloadedPage], datosPartido: Optional[dict] = None):

    auxResult = {}

    if datosPartido is not None:
        auxResult['sinDatos'] = True
        auxResult['alias'] = datosPartido['nombre']

    if datosPag is None:
        return auxResult


    auxResult['URL'] = datosPag.home
    auxResult['timestamp'] = datosPag.timestamp

    fichaData: bs4.BeautifulSoup = datosPag.data

    cosasUtiles: Optional[bs4.BeautifulSoup] = fichaData.find(name='div', attrs={'class': 'datos'})

    if cosasUtiles is not None:
        auxResult.update(procesaCosasUtilesPlantilla(data=cosasUtiles, urlRef=auxResult['URL']))

    auxResult.update(findLocucionNombre(data=fichaData))

    return auxResult

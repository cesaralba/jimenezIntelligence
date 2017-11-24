
from mechanicalsoup import StatefulBrowser
from time import gmtime
from urllib.parse import urlparse,unquote, parse_qs
from collections import defaultdict

URL_BASE =  "http://www.acb.com"

class CalendarioACB(object):

    def __init__(self,config={},url=URL_BASE):
        self.timestamp = gmtime
        self.URLsDownloaded= {}
        self.Partidos = {}
        self.Jornadas = {}

        self.changed = False
        self.url = url
        self.config = config
        self.browser = StatefulBrowser(soup_config={ 'features' : "html.parser"},
                           raise_on_404=True,
                           user_agent="SMparser",
                           )
        if 'verbose' in config:
            self.browser.set_verbose(self.config.verbose)

        if 'debug' in config:
            self.browser.set_debug(self.config.debug)


    def BajaCalendario(self,competicion="LACB",edicion=None):
        self.browser.open(self.url)
        callinks = self.browser.links(link_text="Calendario")
        if len(callinks)==1:
            link=callinks[0]
        else:
            raise SystemError("Too many links to Calendario. {}".format(callinks))

        if not competicion in link['href']:
            raise SystemError("Enlace '{}' no corresponde a competición {}.".format(link['href'],
                                                                                    competicion))
        self.browser.follow_link(link)
        curURL=self.browser.get_url()

        #print(self.browser.get_current_page())
        urlsToDownload = {}
        for li in self.browser.links(url_regex="stspartido.php"):
            liurl = li['href']
            if not liurl in self.URLsDownloaded:
                if not liurl in urlsToDownload:
                    urlsToDownload[liurl] = li
                    self.BajaPartido(dest=li,home=curURL)
                    #break


    def BajaPartido(self,dest=None,home=None):
        partido = Partido(home=home,dest=dest,browser=self.browser )




class Partido(object):

    def __init__(self,dest,home=None,browser=None):

        datosURL=self.AnalizaLinkPartido(dest['href'])
        self.comp = datosURL['cod_competicion']
        self.temp = datosURL['cod_edicion']
        self.game = datosURL['partido']
        self.prorrogas = 0

        if browser is None:
            browser=StatefulBrowser(soup_config={ 'features' : "html.parser"},
                           raise_on_404=True,
                           user_agent="SMparser",
                           )
        if home is None:
            browser.open(dest)
        else:
            browser.open(home)
            browser.follow_link(dest)

        self.url = browser.get_url()
        self.ParsePartido(browser.get_current_page())

    def ParsePartido(self,content):

        #Datos muy sucios
        #partHeader=pagePartido.find("div",{"class":'titulopartidonew'})

        tablasPartido=content.find_all("table",{"class":"estadisticasnew"})
        tabDatosGenerales=tablasPartido[0]
        filas=tabDatosGenerales.find_all("tr")
        celdas=filas[0].find_all("td")

        espTiempo = celdas.pop(0).get_text().split("|")
        print(espTiempo)

        celdas.pop(0)

        for fila in celdas:
            print("--",fila)
        print("\n")

        #print(tabDatosGenerales)



    def AnalizaLinkPartido(self,url):
        #urlcomps = parse_qsl(urlparse(unquote(url))['query'])
        urlcomps = parse_qs(urlparse(unquote(url)).query)
        result={}
        for i in urlcomps:
            result[i]=urlcomps[i][0]
        return result









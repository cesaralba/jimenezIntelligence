from urllib.parse import parse_qs,urlparse,unquote



def ExtraeGetParams(url):
    """
       Devuelve un diccionario con los parámetros pasados en la URL
    """
    #urlcomps = parse_qsl(urlparse(unquote(url))['query'])
    urlcomps = parse_qs(urlparse(unquote(url)).query)
    result={}
    for i in urlcomps:
        result[i]=urlcomps[i][0]
    return result
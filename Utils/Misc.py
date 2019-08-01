import re
from collections import defaultdict
from pathlib import Path
from time import gmtime
from unicodedata import normalize

####################################################################################################################

FORMATOtimestamp = "%Y-%m-%d %H:%M"
FORMATOfecha = "%Y-%m-%d"
PARSERfechaC = "%d/%m/%Y"


class BadString(Exception):
    def __init__(self, cadena=None):
        if cadena:
            Exception.__init__(self, cadena)
        else:
            Exception.__init__(self, "Data doesn't fit expected format")


class BadParameters(Exception):
    def __init__(self, cadena=None):
        if cadena:
            Exception.__init__(self, cadena)
        else:
            Exception.__init__(self, "Wrong (or missing) parameters")


def ExtractREGroups(cadena, regex="."):
    datos = re.match(pattern=regex, string=cadena)

    if datos:
        return datos.groups()
    else:
        return None


def ReadFile(filename):
    with open(filename, "r") as handin:
        read_data = handin.read()
    return {'source': filename, 'data': ''.join(read_data), 'timestamp': gmtime()}


def CompareBagsOfWords(x, y):
    # ['NFC', 'NFKC', 'NFD', 'NFKD']
    NORMA = 'NFKD'

    bogx = set(normalize(NORMA, x).encode('ascii', 'ignore').lower().split())
    bogy = set(normalize(NORMA, y).encode('ascii', 'ignore').lower().split())

    return len(bogx.intersection(bogy))


def CuentaClaves(x):
    if (type(x) is not dict) and (type(x) is not defaultdict):
        raise ValueError("CuentaClaves: necesita un diccionario")

    resultado = defaultdict(int)

    for clave in x:
        valor = x[clave]

        if (type(valor) is not dict) and (type(valor) is not defaultdict):
            print("CuentaClaves: objeto de clave '%s' no es un diccionario" % clave)
            continue

        for subclave in valor:
            resultado[subclave] += 1

    return resultado


def Valores2Claves(x):
    if (type(x) is not dict) and (type(x) is not defaultdict):
        raise ValueError("CuentaClaves: necesita un diccionario")

    resultado = defaultdict(set)

    for clave in x:
        valor = x[clave]
        (resultado[valor]).add(clave)

    return resultado


def DumpDict(x, claves=None):
    if (type(x) is not dict) and (type(x) is not defaultdict):
        raise ValueError("CuentaClaves: necesita un diccionario")

    if claves:
        clavesOk = [clave for clave in claves if clave in x]
    else:
        clavesOk = x.keys()

    result = ["%s -> %s" % (clave, x[clave]) for clave in clavesOk]

    return "\n".join(result)


def Seg2Tiempo(x):
    return "%i:%02i" % (x // 60, x % 60)


def SubSet(lista, idx):
    if not idx:
        return []

    return [lista[x] for x in idx if x < len(lista) and lista[x] is not None]


def deepDictSet(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def deepDict(dic, keys, tipoFinal):
    if len(keys) == 0:
        return dic
    if keys[0] not in dic and len(keys) == 1:
        dic[keys[0]] = (tipoFinal)()

    return deepDict(dic.setdefault(keys[0], {}), keys[1:], tipoFinal)


def generaDefaultDict(listaClaves, tipoFinal):
    """
    Genera un diccionario (defauldict) de 4 niveles de profundidad y cuyo tipo final es el que se indica en el parámetro
    :param listaClaves: lista con los niveles de claves (en realidad se usa la longitud)
    :param tipoFinal: tipo que va almacenar el diccionario más profundo
    :return: defaultdict(defaultdict(...(defaultdict(tipoFinal)))
    """

    def actGenera(objLen, tipo):
        if objLen == 1:
            return defaultdict((tipo))
        else:
            return defaultdict(lambda: actGenera(objLen - 1, tipo))

    return actGenera(len(listaClaves), tipoFinal)


def creaPath(*kargs):
    pathList = [Path(p) for p in kargs]

    return Path.joinpath(*pathList)

import re
from collections import defaultdict
from time import gmtime

####################################################################################################################

FORMATOtimestamp = "%Y-%m-%d %H:%M"
FORMATOfecha = "%Y-%m-%d"


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
    bogx = set(x.lower().split())
    bogy = set(y.lower().split())

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

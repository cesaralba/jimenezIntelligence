import re
from _collections import defaultdict
from unicodedata import normalize

from CAPcore.Misc import cosaCorta, cosaLarga, listize, onlySetElement

NORMADEFECTO = 'NFKD'


class BoWTraductor():
    """
    Clase genérica para un traductor k->v.
    """

    def __init__(self, NORMA=NORMADEFECTO):
        self.NORMA = NORMA  # Valores para NORMA ['NFC', 'NFKC', 'NFD', 'NFKD']
        self.TradConocidas = defaultdict(set)
        self.TradNormalizadas = defaultdict(set)
        self.vn2bow = dict()

    def AddTraduccion(self, clave, valor):
        """
        Añade una nueva traducción conocida
        :param clave: cadena que se traduciría en valor
        :param valor: valor objetivo de la traducción
        :return: None
        """
        self.TradConocidas[clave].add(valor)
        kNorm = NormalizaCadena(clave, self.NORMA)
        self.TradNormalizadas[kNorm].add(valor)
        kBoW = CreaBoW(kNorm)
        self.vn2bow[kNorm] = kBoW

    def CargaTraducciones(self, diccionario):
        """
        CargaTraducciones Importa las traducciones conocidas.
        :param diccionario: Espera un diccionario valor objetivo <- iterable de cadenas validas
        :return:
        """

        for valor, cadenas in diccionario.items():
            parCadenas = listize(cadenas)

            for k in parCadenas:
                self.AddTraduccion(k, valor)

    def BuscaTraduccion(self, x, umbral=0):
        if x in self.TradConocidas:

            if len(self.TradConocidas[x]) == 1:
                auxRes = self.TradConocidas[x]
                return list(auxRes.copy())[0]
        else:
            valNorm = NormalizaCadena(x, NORMA=self.NORMA)
            if valNorm in self.TradNormalizadas:
                auxRes = self.TradNormalizadas[valNorm]
                return onlySetElement(auxRes)

            bowx = CreaBoW(valNorm)
            resultList = [(vny, vnyVal, CompareBagsOfWords(bowx, vnyVal)) for vny, vnyVal in self.vn2bow.items() if
                          CompareBagsOfWords(bowx, vnyVal) > 0]

            fullMatch = [x for x in resultList if len(bowx) == x[2]]

            if fullMatch:
                auxRes = set()
                for sol in fullMatch:
                    auxRes = auxRes.union(self.TradNormalizadas[sol[0]])
                return onlySetElement(auxRes)

            if umbral and resultList:
                # TODO: work this out

                fullMatch = set()
                candidates = defaultdict(set)
                for vny, bowy, coincidences in resultList:
                    if bowx == bowy or bowx.intersection(bowy) == bowx:
                        fullMatch = fullMatch.union(self.TradNormalizadas[vny])
                    else:
                        candidates[coincidences] = candidates[coincidences].union(self.TradNormalizadas[vny])

                if fullMatch:
                    return onlySetElement(fullMatch)

                if candidates:
                    print(candidates)
                    return candidates

        return None


def NormalizaCadena(x, NORMA=NORMADEFECTO):
    """
    Normaliza una cadena. Incluye Unicode -> encode ASCII -> minusculas
    :param x: Cadena.
    :param NORMA: Norma Unicode a la que normalizar
                  (ver https://docs.python.org/3.7/library/unicodedata.html#unicodedata.normalize)
    :return: cadena normalizada
    """

    return normalize(NORMA, x).encode('ascii', 'ignore').lower()


def CreaBoW(x):
    """
    Crea un set con las palabras de una cadena
    :param x: cadena. ASUME que ya está normalizada
    :return:
    """
    return set(x.split())


def CompareBagsOfWords(x, y):
    def setize(x):
        if not isinstance(x, (set, str, bytes)):
            raise TypeError(f"Esperaba cadena o set: {x} -> {type(x)}")
        return x if isinstance(x, set) else set(x.split())

    bogx = setize(x)
    bogy = setize(y)

    result = len(bogx.intersection(bogy))

    return result


def wordPosSet(wordList):
    """
    Crea un diccionario con la posición de cada palabra en una fase. Ojo, devuelve un set de posiciones para tener en
    cuenta que pueda haber más de una aparición. No manipula la frase por lo que cualquier manipulación debe ser hecha
    antes.

    :param wordList: Bien una lista de palabras (frase ya dividida) o una frase (se separa por espacios)
    :return:
    """
    wrkList = wordList
    if isinstance(wordList, list):
        wrkList = wordList
    elif isinstance(wordList, (str, bytes)):
        wordList.split()

    result = defaultdict(set)
    for o, w in enumerate(wrkList):
        result[w].add(o)

    return result


def RetocaNombreJugador(x):
    """
    Dado un "APELLIDOS, NOMBRE", devuelve "NOMBRE APELLIDOS"
    :param x:
    :return:
    """
    PATjug = r'^(?P<apell>.*)\s*,\s*(?P<nombre>.*)$'

    REjug = re.match(PATjug, x)

    if REjug:
        return f"{REjug['nombre']} {REjug['apell']}"

    return x


def comparaNombresPersonas(fr1, fr2, umbral=1):
    def comparaPrefijos(pref1, pref2, result=0):
        if pref1 is None or pref2 is None:
            return result
        # print("CAP compPref",pref1,type(pref1),pref2,type(pref2))
        if pref1 == pref2:
            return result + len(pref1)

        if len(pref1) == 0 or len(pref2) == 0:
            return result

        prefLargo = cosaLarga(pref1, pref2)
        prefCorto = cosaCorta(pref1, pref2)

        for wl in prefLargo:
            for wc in prefCorto:
                if esSigla(wl) or esSigla(wc) and (hazSigla(wl) == hazSigla(wc)):  # Pedro vs P.
                    # print("Siglas!", wl, wc, hazSigla(wl), hazSigla(wc), hazSigla(wl) == hazSigla(wc))
                    return comparaPrefijos(prefLargo.remove(wl), prefCorto.remove(wc), result + 1)

                # Javier vs Javi
                cadLarga = cosaLarga(wl, wc)
                cadCorta = cosaCorta(wl, wc)
                if cadLarga.startswith(cadCorta):
                    return comparaPrefijos(prefLargo.remove(wl), prefCorto.remove(wc), result + 1)

        # TODO: Traducciones conocidas jose -> pepe, josep -> pep, ignacio -> nacho
        # TODO: Nombre compuesto -> siglas juntas   DJ Seeley  <-> Dennis Jerome Seeley (también KC Rivers)

        return result

    if fr1 == fr2:
        return True

    set1 = CreaBoW(fr1)
    set2 = CreaBoW(fr2)

    if set1 == set2:
        return True

    enAmbas = set1.intersection(set2)

    if not enAmbas:
        return False

    acum = len(enAmbas)

    if acum > umbral:  # Mas de umbral coincidencia's es prometedor
        return True

    subsets1 = getSubsets(fr1, enAmbas)
    subsets2 = getSubsets(fr2, enAmbas)

    if len(subsets1['diff']) == 0 or len(subsets2['diff']) == 0:
        return True  # Una de las cadenas es la otra más cosas

    if len(subsets1['pref']) > 0 and len(subsets2['pref']) > 0:
        acum += comparaPrefijos(subsets1['pref'], subsets2['pref'], result=0)

    if len(subsets1['medio']) > 0 and len(subsets2['medio']) > 0:
        acum += len(set(subsets1['medio']).intersection(set(subsets2['medio'])))

    if len(subsets1['resto']) > 0 and len(subsets2['resto']) > 0:
        acum += len(set(subsets1['resto']).intersection(set(subsets2['resto'])))

    return acum > umbral


def esSigla(cadena):
    PATsigla = rb'^[a-z]\.' if isinstance(cadena, bytes) else r'^[a-z]\.'
    REsult = re.match(PATsigla, cadena, re.IGNORECASE)

    return REsult is not None


def hazSigla(cadena):
    result = f"{cadena[0]}."
    return result


def getSubsets(cadenaNorm, elemClave):
    """
    A partir de una cadena y una serie de palabras "clave" dentro de la cadena, devuelve serie de grupos interesantes
    para usar en comparaNombresPersonas. La cadena NO se toca más allá de dividirla en fragmentos
    :param cadenaNorm:
    :param elemClave:
    :return:
    """
    set1 = CreaBoW(cadenaNorm)

    list1 = cadenaNorm.split()
    order1 = wordPosSet(list1)

    soloEn1 = set1.difference(elemClave)

    posInt1 = set()
    for w in elemClave:
        posInt1 = posInt1.union(order1[w])

    pref1 = list1[:min(posInt1)]

    medio1 = [] if len(elemClave) == 1 else [list1[x] for x in range(min(posInt1) + 1, max(posInt1)) if
                                             list1[x] not in elemClave]

    resto1 = list1[(1 + max(posInt1)):]

    result = {'set': set1, 'lista': list1, 'diff': soloEn1, 'pref': pref1, 'medio': medio1, 'resto': resto1}

    return result

import re
from unicodedata import normalize

from _collections import defaultdict

from .Misc import listize, onlySetElement

NORMADEFECTO = 'NFKD'


class BoWTraductor(object):
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
            auxRes = self.TradConocidas[x]
            if len(auxRes) == 1:
                return list(auxRes.copy())[0]
        else:
            valNorm = NormalizaCadena(x, NORMA=self.NORMA)
            if valNorm in self.TradNormalizadas:
                auxRes = self.TradNormalizadas[valNorm]
                return onlySetElement(auxRes)

            else:
                bowx = CreaBoW(valNorm)
                resultList = [(vny, self.vn2bow[vny], CompareBagsOfWords(bowx, self.vn2bow[vny])) for vny in
                              self.vn2bow.keys() if CompareBagsOfWords(bowx, self.vn2bow[vny]) > 0]

                fullMatch = [x for x in resultList if len(bowx) == x[2]]

                if fullMatch:
                    auxRes = set()
                    for sol in fullMatch:
                        auxRes = auxRes.union(self.TradNormalizadas[sol[0]])
                    return onlySetElement(auxRes)

                if umbral:
                    # TODO: work this out

                    if resultList:
                        fullMatch = set()
                        candidates = defaultdict(set)
                        for vny, bowy, coincidences in resultList:
                            if bowx == bowy or bowx.intersection(bowy) == bowx:
                                fullMatch = fullMatch.union(self.TradNormalizadas[vny])
                            else:
                                candidates[coincidences] = candidates[coincidences].union(self.TradNormalizadas[vny])

                        if fullMatch:
                            return onlySetElement(fullMatch)

                        elif candidates:
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
            raise TypeError("Esperaba cadena o set: %s -> %s" % (x, type(x)))
        return x if isinstance(x, set) else set(x.split())

    bogx = setize(x)
    bogy = setize(y)

    result = len(bogx.intersection(bogy))
    # if result>0:
    #     print(result,bogx,bogy)

    return result


def wordPosSet(wordList):
    """
    Crea un diccionario con la posición de cada palabra en una fase. Ojo, devuelve un set de posiciones para tener en
    cuenta que pueda haber más de una aparición. No manipula la frase por lo que cualquier manipulación debe ser hecha
    antes.

    :param wordList: Bien una lista de palabras (frase ya dividida) o una frase (se separa por espacios)
    :return:
    """

    wrkList = wordList if isinstance(wordList, list) else (
        wordList.split() if isinstance(wordList, (str, bytes)) else wordList)
    result = defaultdict(set)
    for w, o in zip(wrkList, range(len(wrkList))):
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
        return "%s %s" % (REjug['nombre'], REjug['apell'])
    else:
        return x
        # raise ValueError("Jugador '%s' no casa RE '%s'" % (x, PATjug))


def comparaFrases(fr1, fr2, umbral=1):
    def comparaPrefijos(pref1, pref2):
        if pref1 == pref2:
            return True
        elif len(pref1) == 0 or len(pref2) == 0:
            return True

        prefLargo = pref2 if len(pref2) > len(pref1) else pref1
        prefCorto = pref1 if len(pref2) > len(pref1) else pref2

        for wl in prefLargo:
            for wc in prefCorto:
                if esSigla(wl) or esSigla(wc):
                    if hazSigla(wl) == hazSigla(wc):
                        print("Siglas!", wl, wc, hazSigla(wl), hazSigla(wc), hazSigla(wl) == hazSigla(wc))
                        return comparaPrefijos(prefLargo.remove(wl), prefCorto.remove(wc))
                cadLarga = wl if len(wl) > len(wc) else wc
                cadCorta = wc if len(wl) > len(wc) else wl

                if cadLarga.startswith(cadCorta):
                    return comparaPrefijos(prefLargo.remove(wl), prefCorto.remove(wc))

        # TODO: Traducciones conocidas jose -> pepe, josep -> pep, ignacio -> nacho
        # TODO: Nombre compuesto -> siglas juntas   DJ Seeley  <-> Dennis Jerome Seeley (también KC Rivers)

        return False

    if fr1 == fr2:
        return True

    set1 = CreaBoW(fr1)
    set2 = CreaBoW(fr2)

    if set1 == set2:
        return True

    enAmbas = set1.intersection(set2)

    result = False

    if not enAmbas:
        return False
    elif len(enAmbas) > umbral:  # Mas de umbral coincidencia's es prometedor
        result |= True

    subsets1 = getSubsets(fr1, enAmbas)
    subsets2 = getSubsets(fr2, enAmbas)

    if len(subsets1['diff']) == 0 or len(subsets2['diff']) == 0:
        return True  # Una de las cadenas es la otra más cosas

    if len(subsets1['pref']) > 0 and len(subsets2['pref']) > 0:
        result |= comparaPrefijos(subsets1['pref'], subsets2['pref'])

    if len(subsets1['medio']) > 0 and len(subsets2['medio']) > 0:
        print("En compMedios", fr1, "(", subsets1['medio'], ") <-> ", fr2, "(", subsets2['medio'], ")")

    if len(subsets1['resto']) > 0 and len(subsets2['resto']) > 0:
        print("En compResto", fr1, "(", subsets1['resto'], ") <-> ", fr2, "(", subsets2['resto'], ")")

    return result


def esSigla(cadena):
    PATsigla = b'^[a-z]\.' if isinstance(cadena, bytes) else r'^[a-z]\.'
    REsult = re.match(PATsigla, cadena, re.IGNORECASE)

    return REsult is not None


def hazSigla(cadena):
    result = "%c." % cadena[0]
    return result


def getSubsets(cadenaNorm, elemClave):
    """
    A partir de una cadena y una serie de palabras "clave" dentro de la cadena, devuelve serie de grupos interesantes
    para usar en comparaFrases. La cadena NO se toca más allá de dividirla en fragmentos
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

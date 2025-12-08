from typing import Optional, Set, List, Dict, Iterable, Type


def copyDictWithTranslation(source: Dict, translation: Optional[Dict] = None, excludes: Optional[Set, List] = None):
    """
    Copia un dict traduciendo las claves (con excludes)
    :param source: dict a copiar
    :param translation: traducciones de las claves
    :param excludes: claves que no se quieren incluir
    :return:
    """
    if translation is None:
        translation = {}
    if excludes is None:
        excludes = set()

    result = {translation.get(k, k): v for k, v in source.items() if k not in excludes}
    return result


def createDictOfType(keys: Iterable, dataType: Type) -> Dict:
    """

    Crea un diccionario con claves indicadas cuyo valor será un tipo predefinido
    :param keys:
    :param dataType:
    :return:
    """
    result = {k: dataType() for k in keys}

    return result

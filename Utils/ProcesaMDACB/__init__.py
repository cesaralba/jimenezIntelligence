from typing import List, Dict, Any, Optional


def auxEsDato(data):
    return (isinstance(data, list) and len(data) == 4 and isinstance(data[3], dict))


def auxProcesaDatosReales(datoAmirar: List, parClave: str) -> Dict[str, Any] | None:
    if not auxEsDato(datoAmirar):
        return None

    dictDato: Dict = datoAmirar[3]
    if 'children' in dictDato:
        listaHijos = [dictDato['children']] if auxEsDato(dictDato['children']) else dictDato['children']
        for child in listaHijos:
            res = auxProcesaDatosReales(child, parClave=parClave)
            if res is not None:
                return res
    elif parClave in dictDato:
        return dictDato

    return None


def extraeDatosRelevantesMD(embData: Dict, claveDeInteres: str) -> Optional[Dict]:
    result = None

    for val in embData.values():
        res = auxProcesaDatosReales(val, parClave=claveDeInteres)
        if res is not None:
            return res

    return result

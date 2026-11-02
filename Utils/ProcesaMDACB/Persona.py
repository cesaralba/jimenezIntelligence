from pprint import pp
from typing import Dict, Any

from CAPcore.Web import DownloadedPage

from Utils.Misc import checkRequiredKeys
from Utils.ProcesaMDACB import extraeDatosRelevantesMD
from Utils.Web import extraePagDataScripts


def extraeDatosBioPersonaMD(pag: DownloadedPage, **kwargs):
    missingKeys = checkRequiredKeys(kwargs, {'internalBio', 'externalBio'})

    if missingKeys:
        missingKeys = ",".join(sorted(map(lambda s: f"'{s}'", missingKeys)))
        raise SyntaxError(f"extraeDatosBioPersonaMD: faltan claves: {missingKeys}")

    claveInt = kwargs['internalBio']
    claveExt = kwargs['externalBio']
    embData = extraePagDataScripts(pag, keyword=claveExt)
    interestingData = extraeDatosRelevantesMD(embData, claveDeInteres=claveExt)

    datosExt = interestingData[claveExt][claveExt]
    datosInt = datosExt[claveInt]

    pp(datosExt)


def extraeTrayectoriaPersonaMD(embData: Dict[str, Any]):
    pass

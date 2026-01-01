from typing import Tuple

from CAPcore.LoggedValue import LoggedValue
from CAPcore.Misc import getUTC

from Utils.Web import sentinel
from .Constants import CLAVESFICHAENTRENADOR
from .FichaPersona import FichaPersona, FichaClubPersona


class FichaEntrenador(FichaPersona):
    def __init__(self, **kwargs):
        changesInfo = {'NuevaFicha': (None, True)}

        super().__init__(NuevaFicha=True, tipoFicha='entrenador', changesInfo=changesInfo, **kwargs)

    def actualizaBio(self, changeInfo=sentinel, **kwargs):
        if changeInfo is sentinel:
            changeInfo = {}
        result = False
        for k in CLAVESFICHAENTRENADOR:
            if k not in kwargs:
                continue
            if getattr(self, k) != kwargs[k]:
                result |= True
                oldV = getattr(self, k)
                setattr(self, k, kwargs[k])
                changeInfo[k] = (oldV, kwargs[k])

        return result

    def infoFichaStr(self) -> Tuple[str, str]:
        prefix = "Ent"
        cadenaStr = "TBD"

        return prefix, cadenaStr

    def nuevaFichaClub(self, **kwargs):
        return FichaClubEntrenador(**kwargs)


class FichaClubEntrenador(FichaClubPersona):
    def __init__(self, **kwargs):
        timestamp = kwargs.get('timestamp', getUTC())

        self.dorsal: LoggedValue = LoggedValue(timestamp=timestamp)

        super().__init__(**kwargs)

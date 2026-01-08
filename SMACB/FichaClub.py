from datetime import datetime
from pprint import pp
from typing import Optional

from CAPcore.DataChangeLogger import DataChangesTuples
from CAPcore.LoggedClass import diffDicts, LoggedClassGenerator
from CAPcore.LoggedValue import LoggedValue, extractValue, setNewValue
from CAPcore.Misc import getUTC

CAMPOSIDFICHACLUBPERSONA = ['persId', 'clubId']
CAMPOSOPERFICHACLUBPERSONA = ['alta', 'baja', 'activo']
EXCLUDEUPDATES = CAMPOSIDFICHACLUBPERSONA + ['alta', 'baja']
CAMPOSFICHACLUBPERSONA = CAMPOSIDFICHACLUBPERSONA + CAMPOSOPERFICHACLUBPERSONA

DataLogger = LoggedClassGenerator(DataChangesTuples)


class FichaClubPersona(DataLogger):

    def __init__(self, persId: str, clubId: str, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        self.persId: Optional[str] = persId
        self.clubId: Optional[str] = clubId
        self.alta: LoggedValue = LoggedValue(timestamp=timestamp)
        self.baja: LoggedValue = LoggedValue(timestamp=timestamp)
        self.activo: LoggedValue = LoggedValue(timestamp=timestamp)

        super().__init__(**kwargs)
        currVals = self.fichaCl2dict()

        self.alta = setNewValue(self.alta, timestamp, timestamp=timestamp)
        if 'activo' not in kwargs:
            self.activo = setNewValue(self.activo, True, timestamp=timestamp)

        self.updateDataFields(excludes=EXCLUDEUPDATES, **kwargs)

        newActivo = extractValue(self.activo)
        if newActivo is not None and not newActivo:
            self.updateDataFields(timestamp=timestamp, baja=timestamp)

        newVals = self.fichaCl2dict()

        self.updateDataLog(changeInfo=diffDicts(currVals, newVals), timestamp=timestamp)

    def update(self, persId: str, clubId: str, **kwargs):
        changes = False
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        if not self.checkPersonId(persId=persId, clubId=clubId):
            objK = {'persId': self.persId, 'clubId': self.clubId}
            newK = {'persId': persId, 'clubId': clubId}

            raise KeyError(f"Actualización de la persona incorrecta. Actual: {objK}. Datos: {newK}")

        currVals = self.fichaCl2dict()
        currActivo = extractValue(self.activo)

        changes |= self.updateDataFields(excludes=EXCLUDEUPDATES, **kwargs)

        newActivo = extractValue(self.activo)

        if (currActivo != newActivo) and (newActivo is not None) and not newActivo:
            changes |= self.updateDataFields(timestamp=timestamp, baja=timestamp)

        newVals = self.fichaCl2dict()

        if not changes:
            return changes

        self.updateDataLog(changeInfo=diffDicts(currVals, newVals), timestamp=timestamp)

        return changes

    def checkPersonId(self, **kwargs):

        return all(getattr(self, k) == kwargs.get(k, None) for k in CAMPOSIDFICHACLUBPERSONA)

    def bajaClub(self, persId: str, clubId: str, timestamp: Optional[datetime] = None):
        if not self.checkPersonId(persId=persId, clubId=clubId):
            objK = {'persId': self.persId, 'clubId': self.clubId}
            newK = {'persId': persId, 'clubId': clubId}

            raise KeyError(f"Actualización de la persona incorrecta. Actual: {objK}. Datos: {newK}")

        return self.update(persId=persId, clubId=clubId, timestamp=timestamp, activo=False)

    def fichaCl2str(self):
        raise NotImplementedError("fichaCl2str tiene que estar en las clases derivadas")

    def varClaves(self):
        raise NotImplementedError("varClaves tiene que estar en las clases derivadas")

    def fichaCl2dict(self):
        result = self.class2dict(keyList=(CAMPOSFICHACLUBPERSONA + self.varClaves()), mapFunc=extractValue)
        return result


class FichaClubJugador(FichaClubPersona):
    SUBCLASSCLAVES = ['dorsal', 'posicion', 'licencia', 'junior']

    def __init__(self, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        self.dorsal: LoggedValue = LoggedValue(timestamp=timestamp)
        self.posicion: LoggedValue = LoggedValue(timestamp=timestamp)
        self.licencia: LoggedValue = LoggedValue(timestamp=timestamp)
        self.junior: LoggedValue = LoggedValue(False, timestamp=timestamp)

        super().__init__(**kwargs)

    def fichaCl2str(self) -> str:
        data = self.fichaCl2dict()

        pp(data)
        return "TBD"

    def varClaves(self):
        return self.SUBCLASSCLAVES


class FichaClubEntrenador(FichaClubPersona):
    SUBCLASSCLAVES = ['dorsal']

    def __init__(self, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())
        self.dorsal: LoggedValue = LoggedValue(timestamp=timestamp)

        super().__init__(**kwargs)

    def fichaCl2str(self) -> str:
        dorsal = extractValue(self.dorsal)
        cadenaStr = "Sin inf puesto"
        if dorsal is not None:
            cadenaStr = "Principal" if dorsal == '1' else f"Ayudante[{dorsal}]"
        return cadenaStr

    def varClaves(self):
        return self.SUBCLASSCLAVES

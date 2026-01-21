from datetime import datetime
from typing import Optional, Any

from CAPcore.DataChangeLogger import DataChangesTuples
from CAPcore.LoggedClass import diffDicts, LoggedClassGenerator, splitCl2Str
from CAPcore.LoggedValue import LoggedValue, extractValue, setNewValue
from CAPcore.Misc import getUTC

CAMPOSIDFICHACLUBPERSONA = ['persId', 'clubId']
EXCLUDEUPDATES = CAMPOSIDFICHACLUBPERSONA + ['alta', 'baja']

DataLogger = LoggedClassGenerator(DataChangesTuples)

y: datetime


class FichaClubPersona(DataLogger):
    funcsValClass2Str = {'alta': lambda v: v.strftime("%Y-%m-%d") if v is not None else "",
                         'baja': lambda v: v.strftime("%Y-%m-%d") if v is not None else "",
                         'activo': lambda v: "Act" if v else "No act"
                         }

    CLASSCLAVES = ['alta', 'baja', 'activo']

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
            print(f"Poniendo baja! {persId} {clubId} {currActivo} {newActivo} ")
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

    def fichaCl2dict(self) -> Any:
        result = self.class2dict(keyList=(self.CLASSCLAVES + self.SUBCLASSCLAVES), mapFunc=extractValue)
        return result

    # def fichaCl2dictStr(self)->Dict:
    #     formatters={}
    #     formatters.update(self.funcsValClass2Str)
    #     formatters.update(self.funcsValSubClass2Str)
    #
    #     aux:Dict[str,Any]=self.fichaCl2dict()
    #
    #     result={k:{'valor':v} for k,v in aux.items()}
    #     for k,v in aux.items():
    #         result[k]={'valor':v}
    #         reprFunc=formatters.get(k,lambda v:f"'{v}'")
    #         result[k]['repr']=reprFunc(v)
    #
    #     return result


class FichaClubJugador(FichaClubPersona):
    SUBCLASSCLAVES = ['dorsal', 'posicion', 'licencia', 'junior']

    funcsValSubClass2Str = {'junior': lambda v: "(Junior)" if v else "",
                            'dorsal': lambda v: f"#{v}" if v else "Sin dorsal",
                            'posicion': lambda v: f"{v}" if v else "No posic",
                            'licencia': lambda v: f"{v}" if v else "No Lic"
                            }

    def __init__(self, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())

        self.dorsal: LoggedValue = LoggedValue(timestamp=timestamp)
        self.posicion: LoggedValue = LoggedValue(timestamp=timestamp)
        self.licencia: LoggedValue = LoggedValue(timestamp=timestamp)
        self.junior: LoggedValue = LoggedValue(False, timestamp=timestamp)

        super().__init__(**kwargs)

    def fichaCl2str(self) -> str:
        auxStr = self.class2dictStr(keyList=self.CLASSCLAVES + self.SUBCLASSCLAVES)
        vals, reprs = splitCl2Str(auxStr)
        valsList = [reprs[k] for k in ['dorsal', 'posicion', 'licencia', 'junior'] if vals[k]]
        strCampos = (",".join(valsList) + ",") if valsList else ""
        result = f"({strCampos}{auxStr['alta']['repr']}->{auxStr['baja']['repr']})"

        return result


class FichaClubEntrenador(FichaClubPersona):
    SUBCLASSCLAVES = ['dorsal']

    funcsValSubClass2Str = {'dorsal': lambda v: "Principal" if v == '1' else f"Ayudante[{v}]"}

    def __init__(self, **kwargs):
        timestamp = kwargs['timestamp'] = kwargs.get('timestamp', getUTC())
        self.dorsal: LoggedValue = LoggedValue(timestamp=timestamp)

        super().__init__(**kwargs)

    def fichaCl2str(self) -> str:
        auxStr = self.class2dictStr(keyList=self.CLASSCLAVES + self.SUBCLASSCLAVES)
        vals, reprs = splitCl2Str(auxStr)
        valsList = [reprs[k] for k in ['dorsal'] if vals[k]]
        strCampos = (",".join(valsList) + ",") if valsList else ""
        result = f"({strCampos}{auxStr['alta']['repr']}->{auxStr['baja']['repr']})"

        return result

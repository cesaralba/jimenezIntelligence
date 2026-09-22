from datetime import datetime
from typing import Set, Dict, Optional, List, Callable, Tuple, Any

from CAPcore.DataChangeLogger import DataChangesTuples
from CAPcore.LoggedDict import LoggedDictDiff
from CAPcore.Misc import onlySetElement

from .CalendarioACB import dictK2partStr
from .Constants import infoJornada
from .FichaClub import FichaClubEntrenador
from .FichaPersona import FichaEntrenador, FichaJugador, FichaPersona
from .PlantillaACB import CambiosPlantillaTipo
from .TemporadaACB import TemporadaACB

DATEFORMATRES = "%Y-%m-%d"


def trataDiffUltClub(clave: str, cambio: Tuple[str, str], temp: TemporadaACB) -> str:
    _ = clave
    if cambio[1] is None:
        cambioStr = f"club: baja en {temp.plantillas[str(cambio[0])].nombreClub()}"
    else:
        club1 = temp.plantillas[str(cambio[1])].nombreClub()
        cambioStr = f"club: {temp.plantillas[str(cambio[0])].nombreClub()} -> {club1}"

    return cambioStr


tradReduc = {'URL': 'nueva URL', 'urlFoto': 'nueva foto', 'ultClub': trataDiffUltClub}
tradNombreClaves: Dict[str, str] = {'licencia': 'cupo', 'nacionalidad': 'pais', 'lugarNac': 'origen'}


# TODO: Ordenar por apellido
def resumenCambioJugadores(cambiosJugadores: dict, temporada: TemporadaACB):
    entList = []

    for jugCod, jugData in cambiosJugadores.items():

        if not jugData:
            continue
        nuevaFicha = ('nuevo' in jugData) and jugData['nuevo']
        cadenasAmostrar: List[str] = []
        fichaEntr: FichaJugador = temporada.fichaJugadores[jugCod]
        chgLogEntr: dict = fichaEntr.changeLog

        entries2show: List[DataChangesTuples] = sorted(chgLogEntr[t] for t in jugData['cambios'])
        chgList = DataChangesTuples.merge(*entries2show)

        cadenasAmostrar.append(fichaEntr.nombreFicha(muestraPartidos=False, muestraInfoPers=True))
        cadenasAmostrar.extend(preparaSalidaPersona(chgList, fichaEntr, nuevaFicha, temporada))

        entList.append(f"* {" ".join(cadenasAmostrar)}")

    return '\n'.join(sorted(entList))


def resumenCambioEntrenadores(cambiosTecnicos: dict, temporada: TemporadaACB):
    entList = []

    for entCod, entData in cambiosTecnicos.items():

        if not entData:
            continue
        nuevaFicha = ('nuevo' in entData) and entData['nuevo']
        cadenasAmostrar: List[str] = []
        fichaEntr: FichaEntrenador = temporada.fichaEntrenadores[entCod]
        chgLogEntr: dict = fichaEntr.changeLog

        entries2show: List[DataChangesTuples] = sorted(chgLogEntr[t] for t in entData['cambios'])
        chgList = DataChangesTuples.merge(*entries2show)

        cadenasAmostrar.append(fichaEntr.nombreFicha(muestraPartidos=False, muestraInfoPers=True))
        cadenasAmostrar.extend(preparaSalidaPersona(chgList, fichaEntr, nuevaFicha, temporada))

        entList.append(f"* {" ".join(cadenasAmostrar)}")

    return '\n'.join(sorted(entList))


def preparaSalidaPersona(chgList: dict[str, list[Any] | dict[Any, Any]], fichaEntr: FichaEntrenador,
                         nuevaFicha: bool | Any, temporada: TemporadaACB) -> List[str]:
    result = []
    if nuevaFicha:
        KEYS2IGNORE = ['nombre', 'alias', 'URL', 'audioURL', 'club']

        result.append("Nueva ficha:")
        for clavePers in fichaEntr.CLASSCLAVES:
            if (clavePers in KEYS2IGNORE) or (clavePers not in chgList['values']):
                continue
            valorFinal = chgList['values'][clavePers]['values'][-1]
            result.append(f"{clavePers.capitalize()}: '{valorFinal}'")
            if 'audioURL' in chgList['values']:
                result.append("Audio nombre")
    else:
        result.append("Cambios:")
        for clavePers in fichaEntr.CLASSCLAVES:
            if clavePers not in chgList['values']:
                continue
            valoresClave = chgList['values'][clavePers]['values']
            cadenaValor = f"'{valoresClave[-1]}'" if valoresClave[
                                                         0] is None else f"'{valoresClave[0]}' -> '{valoresClave[-1]}'"
            result.append(f"{clavePers.capitalize()}:{cadenaValor}")

        if 'URL' in chgList['values']:
            result.append("Cambio URL")
        if 'audioURL' in chgList['values']:
            result.append("Audio nombre")
    if 'club' in chgList['values']:
        clubStrList = []
        clTray = chgList['values']['club']['values']
        if clTray[0] is None:
            clTray = clTray[1:]

        for clStay in clTray:
            if clStay is None:
                clubStrList.append("Sin club")
                continue
            nombreClub = onlySetElement(temporada.tradEquipos['i2c'][clStay])
            stay: FichaClubEntrenador = fichaEntr.fichasClub.get(clStay, None)
            if stay is None:
                clubStrList.append(f"'{nombreClub}' Sin info")
                continue
            clubStrList.append(
                f"{nombreClub} {stay.fichaCl2str()} {temporada.balanceVictorias(pers=fichaEntr, clubId=clStay)}")
        result.append(" ->".join(clubStrList))
    else:
        result.append("Cambio! No nuevaficha")

    return result


def resumenNuevosPartidos(nuevosPartidos: Set[str], temporada: TemporadaACB):
    resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos), key=lambda p: (
        temporada.Partidos[p].fechaPartido, temporada.Partidos[p].jornada))]
    return "\n".join(resumenPartidos)


def textoJugador(temporada: TemporadaACB, idJug: str):
    return f"{temporada.fichaJugadores[idJug].nombreFicha()}"


def dataPlantJug(temporada: TemporadaACB, idJug: str, idClub: str):
    return temporada.plantillas[idClub].jugadores._asdict()[idJug]


def dataPlantTec(temporada: TemporadaACB, idTec: str, idClub: str):
    return temporada.plantillas[idClub].tecnicos._asdict()[idTec]


def textoTecnico(temporada: TemporadaACB, idTec: str, idClub: str):
    auxInfo = dataPlantTec(temporada, idTec, idClub)
    return f"ENT[{auxInfo['dorsal']}] {auxInfo.get('alias', auxInfo.get('nombre', 'NONAME'))}"


def resumenCambioClubes(cambiosClubes: Dict[str, CambiosPlantillaTipo], temporada: TemporadaACB):
    listaCambios = []

    for cl, cambios in cambiosClubes.items():
        if not (cambios.jugadores or cambios.tecnicos or cambios.club):
            continue
        nombreClub = temporada.plantillas[cl].nombreClub()

        cambiosClubList = []

        if cambios.club:
            cambiosClubList.append(f"Cambio en datos del club: {cambios.club.show(compact=True)}")

        if cambios.jugadores:
            cambioJugsList = preparaResumenPlantillasJugadores(cambios, cl, temporada, tradReducDict=tradReduc)

            if cambioJugsList:
                lineaJugadores = "Cambio en jugadores:\n" + "\n".join(sorted(cambioJugsList))
                cambiosClubList.append(lineaJugadores)

        if cambios.tecnicos:
            cambioTecList = preparaResumenPlantillasTecnicos(cambios, cl, temporada, tradReducDict=tradReduc)

            if cambioTecList:
                lineaTecnicos = "Cambio en técnicos:\n" + "\n".join(sorted(cambioTecList))
                cambiosClubList.append(lineaTecnicos)

        if cambiosClubList:
            lineaClub = f"CLUB '{nombreClub}' [{cl}]:\n" + "\n".join(cambiosClubList)
            listaCambios.append(lineaClub)

    if listaCambios:
        return "\n".join(sorted(listaCambios))

    return ""


def preparaResumenPlantillasTecnicos(cambios, cl, temporada: TemporadaACB,
                                     tradReducDict: Optional[Dict[str, str]] = None):
    if tradReducDict is None:
        tradReducDict = {}
    cambioTecList = []

    for idJug in cambios.tecnicos.added:
        cambioTecList.append(f"  * Alta: {textoTecnico(temporada, idJug, cl)}")

    for idJug, dataJug in cambios.tecnicos.changed.items():
        auxDiffchanged = dataJug.changed
        if not auxDiffchanged:
            continue
        if ('activo' in auxDiffchanged) and (not auxDiffchanged['activo'][1]):
            cambioTecList.append(f"  * Baja: {textoTecnico(temporada, idJug, cl)}")
        else:
            changeStr = formateaResumenDiffs(auxDiffchanged, temp=temporada, tradSimplifs=tradReducDict,
                                             tradClaves=tradNombreClaves)
            cambioTecList.append(f"  * Cambios: {textoTecnico(temporada, idJug, cl)}: {changeStr}")

    for idJug, dataJug in cambios.tecnicos.removed.items():
        cambioTecList.append(f"  * BORRADO:{textoTecnico(temporada, idJug, cl)}")
    return cambioTecList


def preparaResumenPlantillasJugadores(cambios, cl, temporada: TemporadaACB,
                                      tradReducDict: Optional[Dict[str, str]] = None):
    if tradReducDict is None:
        tradReducDict = {}
    cambioJugsList = []
    for idJug in cambios.jugadores.added:
        dorsal = dataPlantJug(temporada, idJug, cl)['dorsal']
        cambioJugsList.append(f"  * Alta: Dorsal: {dorsal}. {textoJugador(temporada, idJug)}")
    for idJug, dataJug in cambios.jugadores.changed.items():
        auxJug = dataPlantJug(temporada, idJug, cl)
        dorsal = auxJug['dorsal']
        auxDiffchanged = dataJug.changed
        if not auxDiffchanged:
            continue
        if 'activo' not in auxDiffchanged or auxDiffchanged['activo'][1]:
            changeStr = formateaResumenDiffs(auxDiffchanged, temp=temporada, tradSimplifs=tradReducDict,
                                             tradClaves=tradNombreClaves)
            cambioJugsList.append(f"  * Cambios: Dorsal: {dorsal}. {textoJugador(temporada, idJug)}: {changeStr}")
        else:
            cambioJugsList.append(f"  * Baja: Dorsal: {dorsal}. {textoJugador(temporada, idJug)}")

    for idJug, dataJug in cambios.jugadores.removed.items():
        auxJug = dataPlantJug(temporada, idJug, cl)
        dorsal = auxJug['dorsal']
        cambioJugsList.append(f"  * BORRADO: {textoJugador(temporada, idJug)} Dorsal: {dorsal}")

    return cambioJugsList


def formateaResumenDiffs(colDiffs: Dict[str, Tuple[str, str]], temp: TemporadaACB, tradSimplifs: Optional[
    Dict[str, str | Callable[[str, Tuple[str, str], TemporadaACB], str]]] = None,
                         tradClaves: Dict[str, str] = None) -> str:
    result = ""
    if tradSimplifs is None:
        tradSimplifs = {}
    if tradClaves is None:
        tradClaves = {}

    auxList: List[str] = []
    for k in colDiffs.keys():
        if k in tradSimplifs:
            trad = tradSimplifs[k]
            newVal = trad(k, colDiffs[k], temp) if callable(trad) else trad
            auxList.append(newVal)
            continue
        if str(colDiffs[k][0]) == str(colDiffs[k][1]):
            continue

        nombreClave = tradClaves.get(k, k)
        if colDiffs[k][0] in {None, ""}:
            auxList.append(f"{nombreClave}: '{colDiffs[k][1]}'")
        else:
            auxList.append(f"{nombreClave}: '{colDiffs[k][0]}'->'{colDiffs[k][1]}'")

    if len(auxList) == 0:
        return result

    result = ", ".join(sorted(auxList))

    return result


# TODO: Ordenar partidos por fecha del partido (acutalmente es orden alfabético y dela ja final al principio F,C,J*.S
def resumenCambiosCalendario(cambios: LoggedDictDiff, temporada: TemporadaACB,
                             datosJornadas: Optional[Dict[int, infoJornada]] = None):
    if not cambios:
        return ""

    if datosJornadas is None:
        datosJornadas = {}

    cambiosCalendario = []

    for pk, fh in cambios.added.items():
        claveP = dictK2partStr(temporada.Calendario, pk)
        cambiosCalendario.append(f"* {claveP} Nuevo partido @{fh}")

    for pk in cambios.removed.keys():
        claveP = dictK2partStr(temporada.Calendario, pk, datosJornadas)
        cambiosCalendario.append(f"* {claveP} Partido eliminado")

    for pk, fhs in cambios.changed.items():
        claveP = dictK2partStr(temporada.Calendario, pk)
        hini, hfin = fhs
        cambiosCalendario.append(f"* {claveP} Cambia: pasa de @{hini} a @{hfin}")

    return "\n".join(sorted(cambiosCalendario))


def procesaCambiosClub(cambiosDict: Dict) -> List[str]:
    resultLines = []
    k: str
    for k, chg in cambiosDict['values'].items():
        valChain = []
        newVal: datetime
        for ts, newVal in zip(([None] + chg['timestamps']), chg['values']):
            if ts is None and newVal is None:
                continue
            tsString = f"({ts.strftime(DATEFORMATRES)})" if ts is not None else ""
            valChain.append(f"'{newVal}'{tsString}")
        resultLines.append(f"    * {k.capitalize()}: {'->'.join(valChain)}")

    if resultLines:
        resultLines.insert(0, "  Cambios en información de club")

    return resultLines


# TODO: Ordenar dorsal como (pseudo, 00)numérico en lugar de como cadena
def procesaCambiosClubJugadores(cambiosDict: Dict, eqId: str, temporada: TemporadaACB) -> List[str]:
    resultLines = []
    salidasClub = []

    k: str
    for k in sorted(cambiosDict['values'].keys()):
        chg = cambiosDict['values'][k]
        datosLinea = []
        cambiosValores = []
        entraEnClub = 'addedValue' in chg

        fichaPers: FichaJugador = temporada.fichaJugadores[k]
        datosEstancia = None
        flagMuestraInfoPers = False

        if ('activo' in chg['values']) and not chg['values']['activo']['values'][-1]:
            flagMuestraInfoPers = True
            datosEstancia = fichaPers.infoFichaStr(club=eqId, trads=temporada.tradEquipos)

        if entraEnClub and not datosEstancia:
            datosLinea.append("Nuevo en club")
        datosLinea.append(
            fichaPers.nombreFicha(muestraInfoPers=flagMuestraInfoPers, muestraPartidos=False, muestraFicha=False))
        if datosEstancia:
            datosLinea.append(datosEstancia)
            datosLinea.append(fichaPers.partsClub[eqId].partsClub2str(trads=temporada.tradEquipos))
            datosLinea.append(temporada.balanceVictorias(fichaPers, clubId=eqId))
            if fichaPers.ultClub is not None:
                datosLinea.append(f"-> Dest: {onlySetElement(temporada.tradEquipos['i2c'][fichaPers.ultClub])}")
            else:
                datosLinea.append("-> Dest: Fuera ACB")

            salidasClub.append("    * " + " ".join(datosLinea))
            continue

        if entraEnClub:
            cambiosValores.append(f"Alta: {chg['timestamps'][0].strftime(DATEFORMATRES)}")
        cambiosValores.extend(calculaCambiosDatos(chg, fichaPers))
        datosLinea.append(f"Datos: {','.join(cambiosValores)}")
        resultLines.append("    * " + " ".join(datosLinea))

    if resultLines:
        resultLines.insert(0, "  Cambios en plantilla")

    if salidasClub:
        resultLines.append("    Salidas")
        resultLines.extend(salidasClub)
    return resultLines


def procesaCambiosClubTecnicos(cambiosDict: Dict, eqId: str, temporada: TemporadaACB) -> List[str]:
    resultLines = []
    salidasClub = []

    idPers: str
    for idPers in sorted(cambiosDict['values'].keys()):
        chg = cambiosDict['values'][idPers]
        datosLinea = []
        cambiosValores = []
        entraEnClub = 'addedValue' in chg

        fichaPers: FichaEntrenador = temporada.fichaEntrenadores[idPers]
        datosEstancia = None
        flagMuestraInfoPers = False

        if ('activo' in chg['values']) and not chg['values']['activo']['values'][-1]:
            flagMuestraInfoPers = True
            datosEstancia = fichaPers.infoFichaStr(club=eqId, trads=temporada.tradEquipos)

        if entraEnClub and not datosEstancia:
            datosLinea.append("Nuevo en club")
        datosLinea.append(
            fichaPers.nombreFicha(muestraInfoPers=flagMuestraInfoPers, muestraPartidos=False, muestraFicha=False))
        if datosEstancia:
            datosLinea.append(datosEstancia)
            datosLinea.append(fichaPers.partsClub[eqId].partsClub2str(trads=temporada.tradEquipos))
            datosLinea.append(temporada.balanceVictorias(fichaPers, clubId=eqId))
            datosLinea.append("-> Dest: Fuera ACB")
            if fichaPers.ultClub is not None:
                datosLinea.append(f"-> Dest: {onlySetElement(temporada.tradEquipos['i2c'][fichaPers.ultClub])}")

            salidasClub.append("    * " + " ".join(datosLinea))
            continue

        if entraEnClub:
            cambiosValores.append(f"Alta: {chg['timestamps'][0].strftime(DATEFORMATRES)}")
        cambiosValores.extend(calculaCambiosDatos(chg, fichaPers))
        datosLinea.append(f"Datos: {','.join(cambiosValores)}")
        resultLines.append("    * " + " ".join(datosLinea))

    if resultLines:
        resultLines.insert(0, "  Cambios en tecnicos")

    if salidasClub:
        resultLines.append("    Salidas")
        resultLines.extend(salidasClub)
    return resultLines


def calculaCambiosDatos(chg, datosPers: FichaPersona):
    result = []
    CLAVESAOMITIR = {'id', 'URL', 'activo'}
    trData = datosPers.getAttrNameTranslator(
        translations=datosPers.fichasClub[datosPers.ultClub].getAttrNameTranslator())
    trFunc = datosPers.getAttrFormatters(formatters=datosPers.fichasClub[datosPers.ultClub].getAttrFormatters())
    for subCl in sorted(chg['values']):
        valChain = []
        datosChgClave = chg['values'][subCl]
        if subCl in CLAVESAOMITIR:
            continue
        claveTrad = trData[subCl]

        skipDate: bool = (datosChgClave['values'][0] is None) and (len(datosChgClave['values']) == 2)
        for ts, newVal in zip(([None] + datosChgClave['timestamps']), datosChgClave['values']):
            if ts is None and newVal is None:
                continue
            valTrad = trFunc[subCl](newVal)
            tsString = f"({ts.strftime(DATEFORMATRES)})" if ((ts is not None) and not skipDate) else ""
            valChain.append(f"{valTrad}{tsString}")
        result.append(f" {claveTrad.capitalize()}: {'->'.join(valChain)}")

    return result

from datetime import datetime
from typing import Set, Dict, List, Any

from CAPcore.DataChangeLogger import DataChangesTuples, DataChangesRaw
from CAPcore.LoggedDict import LoggedDictDiff
from CAPcore.Misc import onlySetElement

from .CalendarioACB import dictK2partStr
from .FichaClub import FichaClubEntrenador
from .FichaPersona import FichaEntrenador, FichaJugador, FichaPersona
from .PlantillaACB import CambiosPlantillaTipo, PlantillaACB
from .TemporadaACB import TemporadaACB

DATEFORMATRES = "%Y-%m-%d"


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
    resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(nuevosPartidos,
                                                                  key=lambda p: (temporada.Partidos[p].fechaPartido,
                                                                                 temporada.Partidos[p].jornada))]
    return "\n".join(resumenPartidos)


def textoJugador(temporada: TemporadaACB, idJug: str):
    return f"{temporada.fichaJugadores[idJug].nombreFicha(trads=temporada.tradEquipos)}"


def dataPlantJug(temporada: TemporadaACB, idJug: str, idClub: str):
    return temporada.plantillas[idClub].jugadores._asdict()[idJug]


def textoTecnico(temporada: TemporadaACB, idTec: str):
    return f"{temporada.fichaEntrenadores[idTec].nombreFicha(trads=temporada.tradEquipos)}"


def resumenCambioClubes(cambiosClubes: Dict[str, CambiosPlantillaTipo], temporada: TemporadaACB):
    result = []
    for eqId in sorted(cambiosClubes.keys(), key=lambda s: temporada.plantillas[s].nombreClub()):
        eqData = cambiosClubes[eqId]
        if not eqData:
            continue

        nuevoStr = ""
        if eqData.get('nuevo', False):
            nuevoStr = f" (nuevo en liga, alta: {sorted(eqData['cambios'])[0].strftime(DATEFORMATRES)})"

        datosEq: PlantillaACB = temporada.plantillas[eqId]

        chgLogEntr: dict = datosEq.changeLog

        entries2show: List[DataChangesTuples] = sorted(chgLogEntr[t] for t in eqData['cambios'])

        chgList = DataChangesRaw.merge(*entries2show)

        cambiosClubList = []

        nombreClub = temporada.plantillas[eqId].nombreClub()

        if 'club' in chgList['values']:
            cambiosClubList.extend(procesaCambiosClub(chgList['values']['club']))

        if 'jugadores' in chgList['values']:
            cambiosClubList.extend(
                procesaCambiosClubJugadores(cambiosDict=chgList['values']['jugadores'], eqId=eqId, temporada=temporada))

        if 'tecnicos' in chgList['values']:
            cambiosClubList.extend(
                procesaCambiosClubTecnicos(cambiosDict=chgList['values']['tecnicos'], eqId=eqId, temporada=temporada))

        if not cambiosClubList:
            continue

        if result:
            result.append("")

        result.append(f"Club: [{eqId}] {nombreClub}{nuevoStr}")
        result.extend(cambiosClubList)

    return "\n".join(result)


def preparaResumenPlantillasTecnicos(cambios, temporada: TemporadaACB):
    cambioTecList = []

    for idTec in cambios.tecnicos.added:
        cambioTecList.append(f"  * Alta: {textoTecnico(temporada, idTec)}")

    for idTec, dataTec in cambios.tecnicos.changed.items():
        auxDiffchanged = dataTec.changed
        if not auxDiffchanged:
            continue
        if ('activo' in auxDiffchanged) and (not auxDiffchanged['activo'][1]):
            cambioTecList.append(f"  * Baja: {textoTecnico(temporada, idTec)}")
        else:
            changeStr = ",".join(
                [f"{k}: '{auxDiffchanged[k][0]}'->'{auxDiffchanged[k][1]}'" for k in sorted(auxDiffchanged.keys())])
            cambioTecList.append(f"  * Cambios: {textoTecnico(temporada, idTec)}: {changeStr}")

    for idTec, dataTec in cambios.tecnicos.removed.items():
        cambioTecList.append(f"  * BORRADO:{textoTecnico(temporada, idTec)}")
    return cambioTecList


def preparaResumenPlantillasJugadores(cambios, cl, temporada: TemporadaACB):
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
        if ('activo' in auxDiffchanged) and (not auxDiffchanged['activo'][1]):
            cambioJugsList.append(f"  * Baja: Dorsal: {dorsal}. {textoJugador(temporada, idJug)}")
        else:
            changeStr = ",".join(
                [f"{k}: '{auxDiffchanged[k][0]}'->'{auxDiffchanged[k][1]}'" for k in sorted(auxDiffchanged.keys())])
            cambioJugsList.append(f"  * Cambios: Dorsal: {dorsal}. {textoJugador(temporada, idJug)}: {changeStr}")

    for idJug, dataJug in cambios.jugadores.removed.items():
        auxJug = dataPlantJug(temporada, idJug, cl)
        dorsal = auxJug['dorsal']
        cambioJugsList.append(f"  * BORRADO: {textoJugador(temporada, idJug)} Dorsal: {dorsal}")

    return cambioJugsList


def resumenCambiosCalendario(cambios: LoggedDictDiff, temporada: TemporadaACB):
    if not cambios:
        return ""
    cambiosCalendario = []

    for pk, fh in cambios.added.items():
        claveP = dictK2partStr(temporada.Calendario, pk)
        cambiosCalendario.append(f"* {claveP} Nuevo partido @{fh}")

    for pk in cambios.removed.keys():
        claveP = dictK2partStr(temporada.Calendario, pk)
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

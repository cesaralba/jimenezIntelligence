from datetime import datetime
from pprint import pp
from typing import Set, Dict, List, Any

from CAPcore.DataChangeLogger import DataChangesTuples, DataChangesRaw
from CAPcore.LoggedDict import LoggedDictDiff
from CAPcore.Misc import onlySetElement

from .CalendarioACB import dictK2partStr
from .FichaClub import FichaClubEntrenador
from .FichaPersona import FichaEntrenador, FichaJugador
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
            if clavePers in KEYS2IGNORE:
                continue
            if clavePers not in chgList['values']:
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
        pp(fichaEntr.SUBCLASSCLAVES)
        result.append("Cambio! No nuevaficha")

    return result


def resumenNuevosPartidos(nuevosPartidos: Set[str], temporada: TemporadaACB):
    resumenPartidos = [str(temporada.Partidos[x]) for x in sorted(list(nuevosPartidos), key=lambda p: (
        temporada.Partidos[p].fechaPartido, temporada.Partidos[p].jornada))]
    return "\n".join(resumenPartidos)


def textoJugador(temporada: TemporadaACB, idJug: str):
    return f"{temporada.fichaJugadores[idJug].nombreFicha(trads=temporada.tradEquipos)}"


def dataPlantJug(temporada: TemporadaACB, idJug: str, idClub: str):
    return temporada.plantillas[idClub].jugadores._asdict()[idJug]


def textoTecnico(temporada: TemporadaACB, idTec: str):
    return f"{temporada.fichaEntrenadores[idTec].nombreFicha(trads=temporada.tradEquipos)}"


def resumenCambioClubes(cambiosClubes: Dict[str, CambiosPlantillaTipo], temporada: TemporadaACB):
    result = []
    for eq, eqData in cambiosClubes.items():
        if not eqData:
            continue
        nuevaFicha = ('nuevo' in eqData) and eqData['nuevo']

        datosEq: PlantillaACB = temporada.plantillas[eq]

        chgLogEntr: dict = datosEq.changeLog

        entries2show: List[DataChangesTuples] = sorted(chgLogEntr[t] for t in eqData['cambios'])

        chgList = DataChangesRaw.merge(*entries2show)

        cambiosClubList = []

        nombreClub = temporada.plantillas[eq].nombreClub()

        print(f"Club {nombreClub}")
        if 'club' in chgList['values']:
            print(f"Antes: {len(cambiosClubList)}")
            cambiosClubList.extend(procesaCambiosClub(chgList['values']['club']))
            print(f"Despues: {len(cambiosClubList)}")

        # print(chgList['values'].keys())

        if not cambiosClubList:
            print("Skipping")
            continue

        print(f"Adding result. Antes {len(result)}")
        if result:
            result.append("")
        nuevoStr = " (nuevo en liga)" if nuevaFicha else ""
        result.append(f"Club: {nombreClub}{nuevoStr}")
        result.extend(cambiosClubList)

        print(f"Adding result. Despues {len(result)}")

        continue

        # print(f"-------- {eq}")
        # #pp(eqData)
        # # pp(datosEq.__dict__)
        #
        # pp(datosEq.changeLog)
        # for c in sorted(eqData['cambios']):
        #     print(c)
        #     pp(datosEq.changeLog[c].__dict__)

    print(">result")
    pp(result)
    print("<result")
    return "\n".join(result)

    listaCambios = []

    for cl, cambios in cambiosClubes.items():
        if not (cambios.jugadores or cambios.tecnicos or cambios.club):
            continue
        nombreClub = temporada.plantillas[cl].nombreClub()

        cambiosClubList = []

        if cambios.club:
            cambiosClubList.append(f"Cambio en datos del club: {cambios.club.show(compact=True)}")

        if cambios.jugadores:
            cambioJugsList = preparaResumenPlantillasJugadores(cambios, cl, temporada=temporada)

            if cambioJugsList:
                lineaJugadores = "Cambio en jugadores:\n" + "\n".join(sorted(cambioJugsList))
                cambiosClubList.append(lineaJugadores)

        if cambios.tecnicos:
            cambioTecList = preparaResumenPlantillasTecnicos(cambios, temporada=temporada)

            if cambioTecList:
                lineaTecnicos = "Cambio en técnicos:\n" + "\n".join(sorted(cambioTecList))
                cambiosClubList.append(lineaTecnicos)

        if cambiosClubList:
            lineaClub = f"CLUB '{nombreClub}' [{cl}]:\n" + "\n".join(cambiosClubList)
            listaCambios.append(lineaClub)

    if listaCambios:
        return "\n".join(sorted(listaCambios))

    return ""


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
        resultLines.append(f"    * {k.capitalize()}:{'->'.join(valChain)}")

    if resultLines:
        resultLines.insert(0, "  Cambios en información de club")

    print(">En procesaCambiosClub")
    pp(resultLines)
    print("<En procesaCambiosClub")
    return resultLines

from typing import Set, Dict, Optional, List, Callable, Tuple

from CAPcore.LoggedDict import LoggedDictDiff

from SMACB.CalendarioACB import dictK2partStr
from SMACB.Constants import infoJornada
from SMACB.PlantillaACB import CambiosPlantillaTipo
from SMACB.TemporadaACB import TemporadaACB


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


def resumenCambioJugadores(cambiosJugadores: dict, temporada: TemporadaACB):
    jugList = []
    for jugCod, jugData in cambiosJugadores.items():
        if not jugData:
            continue

        ultClub = temporada.fichaJugadores[jugCod].ultClub
        clubStr = "" if ultClub is None else f"{temporada.plantillas[str(ultClub)].nombreClub()}"

        jugadorStr = f"{temporada.fichaJugadores[jugCod].nombreFicha()}"

        if 'NuevoJugador' not in jugData:
            cambioStr = formateaResumenDiffs(jugData, temp=temporada, tradSimplifs=tradReduc,
                                             tradClaves=tradNombreClaves)
            if cambioStr == "":
                continue
            newLine = f"* {jugadorStr} Cambios: {cambioStr}"

            jugList.append(newLine)
        else:
            jugList.append(f"* {jugadorStr}: NUEVO FICHAJE de {clubStr}")
            # TODO: Poner datos de jugadores

    return '\n'.join(sorted(jugList))


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

from typing import Set, Dict

from CAPcore.LoggedDict import LoggedDictDiff

from SMACB.CalendarioACB import dictK2partStr
from SMACB.PlantillaACB import CambiosPlantillaTipo
from SMACB.TemporadaACB import TemporadaACB


def resumenCambioJugadores(cambiosJugadores: dict, temporada: TemporadaACB):
    jugList = []

    for jugCod, jugData in cambiosJugadores.items():
        if not jugData:
            continue
        ultClub = temporada.fichaJugadores[jugCod].ultClub
        clubStr = "" if ultClub is None else f"{temporada.plantillas[ultClub].nombreClub()}"

        jugadorStr = f"{temporada.fichaJugadores[jugCod].nombreFicha()}"
        if 'NuevaFicha' in jugData:
            jugList.append(f"* Nuevo fichaje de {clubStr}: {jugadorStr}")
        else:
            claves2skip = {'urlFoto'}
            tradClaves = {'licencia': 'Cupo', 'nacionalidad': 'Pais', 'lugarNac': 'Origen', 'nombre': 'Nombre'}
            cambiosJug = []
            for k, v in jugData.items():
                if (k in claves2skip) or (v[0] is None):
                    continue
                if k == 'ultClub':
                    if v[1] is None:
                        cambioStr = f"Club: baja en {temporada.plantillas[v[0]].nombreClub()}"
                    else:
                        club1 = temporada.plantillas[v[1]].nombreClub()
                        cambioStr = f"Club: {temporada.plantillas[v[0]].nombreClub()} -> {club1}"
                else:
                    cambioStr = f"{tradClaves.get(k, k)}: '{v[0]}'->'{v[1]}'"

                cambiosJug.append(cambioStr)
            if 'urlFoto' in jugData:
                cambiosJug.append("Nueva foto")
            if len(cambiosJug) == 0:
                continue
            jugList.append(f"* {jugadorStr} Cambios: {','.join(sorted(cambiosJug))}")

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
            cambioJugsList = preparaResumenPlantillasJugadores(cambios, cl, temporada)

            if cambioJugsList:
                lineaJugadores = "Cambio en jugadores:\n" + "\n".join(sorted(cambioJugsList))
                cambiosClubList.append(lineaJugadores)

        if cambios.tecnicos:
            cambioTecList = preparaResumenPlantillasTecnicos(cambios, cl, temporada)

            if cambioTecList:
                lineaTecnicos = "Cambio en técnicos:\n" + "\n".join(sorted(cambioTecList))
                cambiosClubList.append(lineaTecnicos)

        if cambiosClubList:
            lineaClub = f"CLUB '{nombreClub}' [{cl}]:\n" + "\n".join(cambiosClubList)
            listaCambios.append(lineaClub)

    if listaCambios:
        return "\n".join(sorted(listaCambios))

    return ""


def preparaResumenPlantillasTecnicos(cambios, cl, temporada: TemporadaACB):
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
            changeStr = ",".join(
                [f"{k}: '{auxDiffchanged[k][0]}'->'{auxDiffchanged[k][1]}'" for k in sorted(auxDiffchanged.keys())])
            cambioTecList.append(f"  * Cambios: {textoTecnico(temporada, idJug, cl)}: {changeStr}")

    for idJug, dataJug in cambios.tecnicos.removed.items():
        cambioTecList.append(f"  * BORRADO:{textoTecnico(temporada, idJug, cl)}")
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

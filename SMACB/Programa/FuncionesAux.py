from collections import defaultdict
from math import isnan
from typing import Set, List, Optional, Iterable, Any

import pandas as pd
from CAPcore.Misc import onlySetElement

from SMACB import TemporadaACB as TempACB
from SMACB.Constants import local2espLargo, LocalVisitante, haGanado2esp, infoJornada, POLABELLIST, POLABEL2ABREV, \
    LOCALNAMES
from SMACB.Programa.Clasif import infoClasifEquipoLR, calculaClasifEquipoLR, infoEquipoPO, infoSerieEquipoPO
from SMACB.Programa.Constantes import nombresClasif, criterioDesempateCruces
from SMACB.TemporadaACB import TemporadaACB
from Utils.FechaHora import NEVER, secs2TimeStr


def auxCalculaBalanceStrSuf(record: infoClasifEquipoLR, addPendientes: bool = False, currJornada: int = None,
                            addPendJornada: bool = False, jornadasCompletas: Set[int] = None
                            ) -> str:
    if jornadasCompletas is None:
        jornadasCompletas = set()

    textoAux = ""
    if currJornada is not None:
        pendJornada = currJornada not in record.Jjug
        pendientes = [p for p in range(1, currJornada) if p not in record.Jjug]
        adelantados = [p for p in record.Jjug if (p > currJornada) and (p not in jornadasCompletas)]
        textoAux = ("" + ("J" if (pendJornada and addPendJornada) else "") + ("P" * len(pendientes)) + (
                "A" * len(adelantados)))

    strPendiente = f" ({textoAux})" if (addPendientes and textoAux) else ""

    return strPendiente


def auxCalculaBalanceStr(record: infoClasifEquipoLR, addPendientes: bool = False, currJornada: int = None,
                         addPendJornada: bool = False, jornadasCompletas: Set[int] = None
                         ) -> str:
    strPendiente = auxCalculaBalanceStrSuf(record, addPendientes, currJornada, addPendJornada, jornadasCompletas)
    victorias = record.V
    derrotas = record.D
    texto = f"{victorias}-{derrotas}{strPendiente}"

    return texto


def auxCalculaInfoPO(datosJornada: infoJornada, recordLR: infoClasifEquipoLR, posicLR, recordPO: infoEquipoPO,
                     **kwargs):
    tempData: Optional[TemporadaACB] = kwargs.get('tempData', None)
    incluyeAct: bool = kwargs.get('incluyeAct', False)

    result = []
    result.append(("LR", f"{recordLR.V}-{recordLR.D},{posicLR}º"))
    for fase in POLABELLIST:
        if fase.lower() not in recordPO.fases:
            continue
        if fase.lower() == datosJornada.fasePlayOff.lower():
            continue
        recFase: infoSerieEquipoPO = recordPO.fases[fase]
        rival = f"{onlySetElement(tempData.tradEquipos['i2c'][recFase.idRival])}" if tempData else ""

        result.append((fase, f"{recFase.V}-{recFase.D}&nbsp;{rival}"))

    if incluyeAct:
        if datosJornada.fasePlayOff in recordPO.fases:
            recFase: infoSerieEquipoPO = recordPO.fases[datosJornada.fasePlayOff]
            result.append((datosJornada.fasePlayOff, f"{recFase.V}-{recFase.D}"))
        else:
            result.append((datosJornada.fasePlayOff, "0-0"))

    return result


def auxCalculaFirstBalNeg(clasif: list[infoClasifEquipoLR]):
    for posic, eq in enumerate(clasif):
        victs = eq.V
        derrs = eq.D

        if derrs > victs:
            return posic + 1
    return None


def partidoTrayectoria(partido: TempACB.filaTrayectoriaEq, datosTemp: TemporadaACB):
    strFecha = partido.fechaPartido.strftime(FMTECHACORTA) if partido.fechaPartido != NEVER else "TBD"
    etiqLoc = "vs " if partido.esLocal else "@"
    datosJor: infoJornada = partido.infoJornada

    textRival = f"{etiqLoc}{partido.equipoRival.nombcorto}"
    strRival = f"{strFecha}: {textRival}"

    strResultado = None
    if not partido.pendiente:
        if datosJor.esPlayOff:
            # TODO: estado de la serie
            strRival = f"{strFecha}: {textRival}"
        else:
            clasifAux = calculaClasifEquipoLR(datosTemp, partido.equipoRival.abrev, partido.fechaPartido)
            clasifStr = auxCalculaBalanceStr(clasifAux, addPendientes=True, currJornada=int(partido.jornada),
                                             addPendJornada=False)
            strRival = f"{strFecha}: {textRival} ({clasifStr})"
        marcador = partido.resultado._asdict()
        locEq = local2espLargo[partido.esLocal]
        locGanador = local2espLargo[partido.esLocal and partido.haGanado]
        for loc in LocalVisitante:
            marcador[loc] = str(marcador[loc])
            if loc == locGanador:
                marcador[loc] = f"<b>{marcador[loc]}</b>"
            if loc == locEq:
                marcador[loc] = f"<u>{marcador[loc]}</u>"

        resAux = [marcador[loc] for loc in LocalVisitante]
        strResultado = f"{'-'.join(resAux)} ({haGanado2esp[partido.haGanado]})"
    return strRival, strResultado


def GENERADORETTIRO(*kargs, **kwargs):
    return lambda f: auxEtiqTiros(f, *kargs, **kwargs)


def GENERADORETREBOTE(*kargs, **kwargs):
    return lambda f: auxEtiqRebotes(f, *kargs, **kwargs)


def GENERADORFECHA(*kargs, **kwargs):
    return lambda f: auxEtFecha(f, *kargs, **kwargs)


def GENERADORTIEMPO(*kargs, **kwargs):
    return lambda f: auxEtiqTiempo(f, *kargs, **kwargs)


def GENMAPDICT(*kargs, **kwargs):
    return lambda f: auxMapDict(f, *kargs, **kwargs)


def GENERADORCLAVEDORSAL(*kargs, **kwargs):
    return lambda f: auxKeyDorsal(f, *kargs, **kwargs)


def auxEtiqRebotes(df, entero: bool = True) -> str:
    if isnan(df['R-D']):
        return "-"

    formato = "{:3}+{:3} {:3}" if entero else "{:5.1f}+{:5.1f} {:5.1f}"

    valores = [int(v) if entero else v for v in [df['R-D'], df['R-O'], df['REB-T']]]

    result = formato.format(*valores)

    return result


def auxEtiqTiempo(df, col='Segs'):
    t = df[col]
    if isnan(t):
        return "-"

    return secs2TimeStr(t)


def auxEtiqTiros(df, tiro, entero=True):
    formato = "{:3}/{:3} {:5.1f}%" if entero else "{:5.1f}/{:5.1f} {:5.1f}%"

    etTC = f"T{tiro}-C"
    etTI = f"T{tiro}-I"
    etTpc = f"T{tiro}%"

    if df[etTI] == 0.0 or isnan(df[etTI]):
        return "-"

    valores = [int(v) if entero else v for v in [df[etTC], df[etTI]]] + [df[etTpc]]

    result = formato.format(*valores)

    return result


FMTECHACORTA = "%d-%m"


def auxEtFecha(f, col, formato=FMTECHACORTA):
    if f is None:
        return "-"

    dato = f[col]
    result = "-" if pd.isnull(dato) else dato.strftime(formato)

    return result


def auxMapDict(f, col, lookup):
    if f is None:
        return "-"

    dato = f[col]
    result = lookup.get(dato, "-")

    return result


def auxKeyDorsal(f, col):
    if f is None:
        return "-"

    dato = f[col]

    try:
        auxResult = int(dato)
    except ValueError:
        auxResult = 999

    result = -1 if dato == "00" else auxResult

    return result


def auxJugsBajaTablaJugs(datos: pd.DataFrame, colActivo=('Jugador', 'Activo')) -> list[int]:
    """
    Devuelve las filas con jugadores que figuran como dados de baja (para ser más preciso, no como Alta)
    :param datos: dataframe con datos para tabla de jugadores
    :param colActivo: columna que contiene si el jugador está activo
    :return: lista con las filas del dataframe (comienza en 0) con jugadores así
    """
    result = []

    # No hay datos
    if colActivo not in datos.columns:
        return result

    estadoJugs = datos[colActivo]

    # Si son todos de baja, nos da igual señalar
    if all(estadoJugs) or all(not x for x in estadoJugs):
        return result

    result = [i for i, estado in enumerate(list(estadoJugs)) if not estado]

    return result


def auxBold(data):
    return f"<b>{data}</b>"


def equipo2clasif(clasifLiga, abrEq):
    result = None

    for pos, eqData in enumerate(clasifLiga, start=1):
        if abrEq in eqData.abrevsEq:
            return pos, eqData

    return result


def etiquetasClasificacion(clasif: List[infoClasifEquipoLR]) -> List[nombresClasif]:
    """
    Prepara una lista con información para usar en las tablas con todos los equipos
    :param clasif: Clasif de la liga en SMACB.Programa.Globals
    :return: Lista de tuplas con
    """
    result = []

    for i, eq in enumerate(clasif, start=1):
        aux = {'pos': i, 'abrev': eq.abrevAusar, 'nombre': eq.nombreCorto}
        result.append(nombresClasif(**aux))

    return result


def auxLabelEqTabla(nombre: str, abrev: str) -> str:
    return f"{nombre} (<b>{abrev}</b>)"


def auxCruceDiag(diag, ponBal=False, ponDif=False) -> str:
    strSep = "<br/>" if (ponBal and ponDif) else ""
    strBal = diag['balanceTotal'] if ponBal else ""
    strDif = f"({diag['diffP']})" if ponDif else ""
    return f"{strBal}{strSep}{strDif}"


def auxLigaDiag(diag, ponBal=False, ponSuf=False) -> str:
    strSep = " " if (ponBal or ponSuf) else ""
    strBal = diag['balanceTotal'] if ponBal else ""
    strSuf = f"{diag.get('sufParts', '')}" if ponSuf and ('sufParts' in diag) and (diag['sufParts'] != "") else ""
    return f"{strBal}{strSep}{strSuf}"


def auxCruceTotalPend(conts):
    return f"{conts['Pdte']}:{conts['PendV']}/{conts['PendD']}"


def auxCruceTotalResuelto(conts, clavesAmostrar: List[str]):
    strCrits = "/".join(map(str, [conts['crit'][crit] for crit in clavesAmostrar]))

    return f"{conts['G']}-{conts['P']} {strCrits}"


def auxCruceResuelto(data):
    auxStr = ""
    if data[1] != 'EmpV':  # EmpV es que ha ganado los 2 partidos
        auxStr = f" {criterioDesempateCruces[data[1]]['Clave']}+{data[2]}"

    return f"<b>{data[0]}</b><br/>{auxStr}"


def auxCrucePendiente(data):
    auxStr = f" {data[1]}+{data[2]}"

    return f"<b>{data[0]}</b><br/>{auxStr}"


def auxCruceTotales(data):  # , clavesAmostrar: List[str]
    # strCritsRes = "/".join(map(str, [data['criterios']['res'][crit] for crit in clavesAmostrar]))
    # strCritsPend = "/".join(map(str, [data['criterios']['res'][crit] for crit in ['L', 'V']]))
    strRes = f"<b>Rs:</b>{data['Resueltos']}"  # ({strCritsRes})
    strPend = f"<b>Pd:</b>{data['Pdtes']}"  # ({strCritsPend})

    return f"{strRes}<br/>{strPend}"


def auxTablaLigaPartJugado(part):
    return f"J:{part[2]}<br/><b>{part[3]}</b>"


def auxTablaLigaPartPendiente(part):
    return f"J:{part[2]}<br/>@{part[3]}"


def auxLeyendaCrucesResueltos(clavesAMostrar: List[str]) -> str:
    listaLeyendas = [(criterioDesempateCruces[k]['Clave'], criterioDesempateCruces[k]['Leyenda']) for k in
                     clavesAMostrar]
    leyendaList = [f"<b>{clave}</b>: {leyenda}" for clave, leyenda in listaLeyendas if clave != ""]
    if len(leyendaList) == 0:
        return ""

    result = "<b>Criterio de desempates</b>:" + (",".join(leyendaList)) + "."
    return result


def auxLeyendaCrucesTotalResueltosEq(clavesAMostrar: List[str]) -> str:
    listaLeyendas = [(criterioDesempateCruces[k]['Clave'], criterioDesempateCruces[k]['Leyenda']) for k in
                     clavesAMostrar]
    leyendaList = [f"{leyenda if clave != '' else 'No empate'}" for clave, leyenda in listaLeyendas]

    result = "<b>Total resuelto de equipo</b>: Balance resueltos y forma de ganar (" + ("/".join(leyendaList)) + ")."
    return result


def auxLeyendaCrucesTotalResueltos(data):
    listaLeyendas = [(k, criterioDesempateCruces[k]['Clave'], criterioDesempateCruces[k]['Leyenda']) for k in
                     data['clavesAmostrar']]
    leyendaList = [f"<b>{leyenda if clave != '' else 'No empate'}</b>: {data['datosTotales']['criterios']['res'][k]}"
                   for k, clave, leyenda in listaLeyendas]

    result = "<b>Total resueltos: motivo</b>: " + (" ,".join(leyendaList)) + "."
    return result


def auxLeyendaCrucesTotalPendientes(data):
    result = (f"<b>Total pendientes: ganador precedente</b>: <b>Local</b>: "
              f"{data['datosTotales']['criterios']['pend'].get('L', 0)}, <b>Visit"
              f"ante</b>: {data['datosTotales']['criterios']['pend'].get('V', 0)}.")
    return result


def auxLeyendaRepartoVictPorLoc(data):
    auxList = [f"<b>{loc}</b>: {data['Victoria'][loc]}" for loc in LocalVisitante]
    result = "<b>Reparto de victorias</b>: " + ", ".join(auxList)

    return result


def jor2StrCab(data: infoJornada):
    if data.esPlayOff:
        rondaStr = {'final': 'Fin', 'semifinales': 'Sem', '1/4 de final': 'Cua', '1/8 de final': 'Oct'}[
            data.fasePlayOff.lower()]
        return f"{rondaStr} <b>{data.partRonda:1}</b>"

    return f"J: <b>{data.jornada:2}</b>"


def presTrayectoriaPlayOff(data) -> str:
    auxResult = []
    for fase, res in data:
        if fase == "LR":
            auxResult.append(f"<b>{fase}</b>:{res}")
        else:
            auxResult.append(f"<b>{POLABEL2ABREV[fase]}</b>:{res}")
    return " ".join(auxResult)


def auxEtiqPartido(tempData: TemporadaACB, rivalAbr, **kwargs):
    esLocal = kwargs.get('esLocal', None)
    locEq = kwargs.get('locEq', None)
    usaAbr = kwargs.get('usaAbr', False)
    usaLargo = kwargs.get('usaLargo', False)

    if (esLocal is None) and (locEq is None):
        raise ValueError("auxEtiqPartido: debe aportar o esLocal o locEq")

    auxEsLocal = esLocal if (esLocal is not None) else (locEq in LOCALNAMES)

    prefLoc = "vs " if auxEsLocal else "@"

    ordenNombre = -1 if usaLargo else 0

    nombre = rivalAbr if usaAbr else sorted(tempData.Calendario.tradEquipos['c2n'][rivalAbr], key=len)[ordenNombre]

    result = f"{prefLoc}{nombre}"

    return result


def esEstCreciente(estName: str, catsCrecientes: set | dict | list | None = None, meother: str = "Eq"):
    """
    Devuelve si una columna de estadísticas es ascendente (mejor cuanto menos) o no
    :param estName: Nombre del estadístico a comprobar (de una lista)
    :param catsCrecientes: lista de estadísticos que son ascendentes (mejor cuanto menos: puntos encajados o balones
    perdidos)
    :param meother: si se trata de mi equipo o del rival (invierte el orden)
    :return: bool
    """
    auxCreciente = {} if catsCrecientes is None else catsCrecientes
    return (meother == "Eq") == (estName in auxCreciente)


def esEstIgnorable(col: tuple, estadObj: str = 'mean', cats2ignore: Iterable | None = None):
    auxCats2Ignore = {} if cats2ignore is None else cats2ignore

    kEq, kMagn, kEst = col

    return (kEst != estadObj) or (kEq == 'Info') or (kMagn in auxCats2Ignore)


def calculaEstadsYOrdenLiga(dataTemp: TemporadaACB, fecha: Any | None = None, estadObj: str = 'mean',
                            catsAscending: Iterable | None = None, cats2ignore: Iterable | None = None
                            ):
    paramMethod = 'min'
    paramNAoption = {True: 'top', False: 'bottom'}

    def calculaTargetCols(cats2ignore, catsAscending, colList, dfEstads, estadObj):
        result = defaultdict(list)
        for col in dfEstads.columns:
            kEq, kMagn, _ = col

            if esEstIgnorable(col, estadObj=estadObj, cats2ignore=(cats2ignore or {})):
                continue

            colList.append(col)
            isAscending = esEstCreciente(kMagn, catsAscending, kEq)

            result[isAscending].append(col)

        return result

    def ordenaTargetCols(colList, dfEstads, paramMethod, paramNAoption, targetCols):
        rankDF = {}
        for asctype in targetCols:
            rankDF[asctype] = dfEstads[targetCols[asctype]].rank(axis=0, method=paramMethod,
                                                                 na_option=paramNAoption[asctype], ascending=asctype)
        resultRank = pd.concat(rankDF.values(), axis=1)[colList]
        return resultRank

    colList = []

    dfEstads: pd.DataFrame = dataTemp.dfEstadsLiga(fecha=fecha)

    targetCols = calculaTargetCols(cats2ignore, catsAscending, colList, dfEstads, estadObj)

    resultRank = ordenaTargetCols(colList, dfEstads, paramMethod, paramNAoption, targetCols)

    result = dfEstads[colList]

    return result, resultRank

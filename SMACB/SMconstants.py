from babel.numbers import decimal

MAXIMOextranjeros = 2
MINIMOnacionales = 4

PRESUPUESTOinicial = 6500000.0
PRECIOpunto = 70000.0

POSICIONES = {'posicion1': 'Base', 'posicion3': 'Alero', 'posicion5': 'Pivot'}
CUPOS = ['Extracomunitario', 'Español', 'normal']

LISTACOMPOS = {'puntos': 'P', 'rebotes': 'REB-T', 'triples': 'T3-C', 'asistencias': 'A'}

BONUSVICTORIA = 1.2


def calculaValSuperManager(valoracion, haGanado=False):
    return round(
        decimal.Decimal.from_float(float(valoracion) * (BONUSVICTORIA if (haGanado and (valoracion > 0)) else 1.0)), 2)


def buildPosCupoIndex():
    indexResult = dict()

    aux = 0
    for pos in POSICIONES:
        indexResult[pos] = dict()
        for cupo in CUPOS:
            indexResult[pos][cupo] = aux
            aux += 1
    return indexResult

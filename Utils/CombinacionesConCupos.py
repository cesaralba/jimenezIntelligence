
from SMACB.SMconstants import MAXIMOextranjeros,MINIMOnacionales
from copy import copy

jugPorPos = [ 3 , 4 , 4 ]

#Posiciones //3 = 0 Bases, //3 = 1 Aleros, // = 2 Pivots
#Cupos: % 3 = 0 Extra, %3 = 1 Nacionales, %3 = 2 Resto

def GeneraCombinaciones():
    listaPos = [None] * 9
    result = []

    def CuentaCupos(rango,offset):
        result = 0
        for i in range(3):
            result += rango[i * 3 + offset]

        return result

    def CheckCuentaPosiciones(rango):
        contPos = [ 0 ] * 3

        for i in range(len(rango)):
            contPos[ i // 3 ] += rango[i]

        for i in range(len(contPos)):
            if contPos[i] != jugPorPos[i]:
                return False
        return True


    def CombinacionesConCupo(rango,depth=0):
        nonlocal result

        tamRange=jugPorPos[ depth // 3 ]

        if depth % 3 == 0:
            tamRange = 2 #Max 2 extracom

        for rango[depth] in range(tamRange+1):
            if (depth + 1 < len(rango)):
                CombinacionesConCupo(rango, depth+1)
            else:
                if (sum(rango)) != 11:
                    continue

                if not CheckCuentaPosiciones(rango):
                    continue

                if (CuentaCupos(rango,0)) > MAXIMOextranjeros:
                    continue

                if (CuentaCupos(rango,1)) < MINIMOnacionales:
                    continue
                print(rango)

                result.append(copy(rango))

    CombinacionesConCupo(listaPos, depth=0)

    return result


if __name__ == '__main__':
    print(len(GeneraCombinaciones()))

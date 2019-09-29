# -*- coding: utf-8 -*-

from time import gmtime, strftime


class LigaSM(object):
    def __init__(self, id, nombre):
        self.id = id
        self.nombre = nombre
        self.timestamp = gmtime()

        self.descargas = dict()
        self.descargaJornada = dict()
        self.ultDescarga = None

    def nuevoEstado(self, datos):
        ahora = gmtime()
        ahoraKey = strftime("%Y%m%d-%H%M%S", ahora)
        if self.ultDescarga is None:
            self.ultDescarga = ahoraKey
            self.descargas[ahoraKey] = datos
            ultJornada = max(datos['jornadas']) if datos['jornadas'] else 0
            self.descargaJornada[ultJornada] = ahoraKey
            return True
        else:
            if datos != self.descargas[self.ultDescarga]:
                currJornadas = set(self.descargas[self.ultDescarga]['jornadas'].keys())
                datosJornadas = set(datos['jornadas'].keys())
                diffJor = datosJornadas - currJornadas
                self.ultDescarga = ahoraKey
                self.descargas[ahoraKey] = datos

                if diffJor:
                    ultJornada = max(diffJor)
                    self.descargaJornada[ultJornada] = ahoraKey

                return True

        return False

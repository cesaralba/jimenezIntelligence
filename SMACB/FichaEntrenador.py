from .FichaPersona import FichaPersona

sentinel=object

class FichaEntrenador(FichaPersona):
    def __init__(self, **kwargs):
        changesInfo = {'NuevoEntrenador': True}

        dataConocida = {'tipoFicha': 'entrenador', 'changesInfo': changesInfo}
        dataConocida.update(kwargs)
        super().__init__(**dataConocida)


    def actualizaBio(self, data)->bool:
        # Los entrenadores tienen las mismas cosas que FichaPersona, los jugadores necesitarán tratamiento específico
        result=False
        result |= self.actualizaBioBasic(**data)

        return result

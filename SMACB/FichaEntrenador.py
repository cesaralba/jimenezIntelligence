from .FichaPersona import FichaPersona


class FichaEntrenador(FichaPersona):
    def __init__(self,**kwargs):
        self.tipoFicha = 'entrenador'

        super(FichaEntrenador,self).__init__(tipoFicha='entrenador',**kwargs)

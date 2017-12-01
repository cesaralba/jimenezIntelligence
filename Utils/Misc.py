import re

####################################################################################################################

class BadStringException(Exception):
    def __init__(self, cadena):
        if cadena:
            Exception.__init__(self, cadena)
        else:
            Exception.__init__(self,"Data doesn't fit expected format")

def ExtractREGroups(cadena,regex="."):
    datos=re.match(pattern=regex,string=cadena)

    if datos:
        return datos.groups()
    else:
        return None
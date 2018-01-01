import re

####################################################################################################################


class BadStringException(Exception):
    def __init__(self, cadena):
        if cadena:
            Exception.__init__(self, cadena)
        else:
            Exception.__init__(self, "Data doesn't fit expected format")


def ExtractREGroups(cadena, regex="."):
    datos = re.match(pattern=regex, string=cadena)

    if datos:
        return datos.groups()
    else:
        return None


def ReadFile(filename):
    with open(filename, "r") as handin:
        read_data = handin.read()
    return {'source': filename, 'data': ''.join(read_data)}

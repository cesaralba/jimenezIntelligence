from time import struct_time, strftime


def Time2Str(timeref: struct_time):
    """
    Vuelca estructura de fecha con hora (si es distinta de 0:00). Ok, no es genérica pero aún no hay partidos ACB a
    media noche
    :param timeref:
    :return:
    """
    format = "%d-%m-%Y" if (timeref.tm_hour == 0 and timeref.tm_min == 0) else "%d-%m-%Y %H:%M"

    result = strftime(format, timeref)

    return result

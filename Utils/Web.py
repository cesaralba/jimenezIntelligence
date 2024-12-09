import re

# https://effbot.org/zone/default-values.htm#what-to-do-instead
sentinel = object()


def getObjID(objURL, clave='id', defaultresult=sentinel):
    PATid = r'^.*/' + clave + r'/(?P<id>\d+)(/.*)?'
    REid = re.match(PATid, objURL)

    if REid:
        return REid.group('id')

    if defaultresult is sentinel:
        raise ValueError(f"getObjID '{objURL}' no casa patrón '{PATid}' para clave '{clave}'")

    return defaultresult

from typing import Iterable, Any, Sized, Hashable, Set


def anyElement(s:Iterable)-> Any:

    try:
        return next(iter(s))
    except StopIteration:
        return None

def checkRequiredKeys(myObject,reqKeys:Iterable[Hashable]) -> Set[Hashable]:
    """
    Returns the list of missing required keys from an object
    :param myObject: something where "in" works (aka, it has __contains__)
    :param reqKeys: list of things that should be in myObject
    :return: a set with missing elements from reqKeys
    """
    result = {k for k in reqKeys if k not in myObject}

    return result

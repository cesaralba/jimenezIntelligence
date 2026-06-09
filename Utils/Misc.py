from typing import Iterable, Any, Sized


def anyElement(s:Iterable)-> Any:

    try:
        return next(iter(s))
    except StopIteration:
        return None

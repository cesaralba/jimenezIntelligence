from typing import Iterable, Dict, Callable, Type, Sequence, Hashable, Union


def sortedByStringLength(data: Iterable[str], reverse: bool = False) -> Iterable[str]:
    return sorted(data, key=lambda x: (len(x), x), reverse=reverse)


def createDictFromGenerator(keys: Sequence[Hashable], genFunc: Union[Type, Callable]) -> Dict:
    """
    Creates a Dict with the result of a generator.
    :param keys:
    :param genFunc:
    :return:
    """

    result = {k: genFunc() for k in keys}

    return result

from typing import Iterable


def sortedByStringLength(data: Iterable[str], reverse: bool = False) -> Iterable[str]:
    return sorted(data, key=lambda x: (len(x), x), reverse=reverse)

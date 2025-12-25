from typing import Dict, Optional, Any

from configargparse import Namespace


def createArgs(*args: Optional[Dict, Namespace]) -> Namespace:
    """
    Creates a Namespace (result of argparse or configargparse) from other namespaces and/or dicts
    :param args:
    :return: Namespace that merges the parameters in the order they are provided. Later value overrides previous
    """
    auxResult = {}

    for arg in args:
        if arg is None:
            continue
        if isinstance(arg, Namespace):
            auxResult.update(arg.__dict__)
        elif isinstance(arg, dict):
            auxResult.update(arg)

    result = Namespace(**auxResult)

    return result


def GetParam(args: Namespace, paramName: str, defValue=None) -> Any:
    return getattr(args, paramName, defValue)

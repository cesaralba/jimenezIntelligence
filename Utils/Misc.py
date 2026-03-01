# Funciones de conveniencia que acabarán en CAPCORE

# def sortedByStringLength(data: Iterable[str], reverse: bool = False) -> Iterable[str]:
#     return sorted(data, key=lambda x: (len(x), x), reverse=reverse)
#
#
# def createDictFromGenerator(keys: Sequence[Hashable], genFunc: Union[Type, Callable]) -> Dict:
#     """
#     Creates a Dict with the result of a generator.
#     :param keys:
#     :param genFunc:
#     :return:
#     """
#
#     result = {k: genFunc() for k in keys}
#
#     return result
#
#
# def iterable2quotedString(data: Iterable[str], charQuote: str = "'", mergedStr: str = ", ") -> str:
#     result = mergedStr.join(f"{charQuote}{s}{charQuote}" for s in sorted(data))
#     return result
#
#
# def getObjLoggedDictDiff(obj: object, newData: Dict[str, Any], INCLUDES=None,
#                          EXCLUDES=None) -> Dict[str, Tuple[Any, Any]]:
#     """
#
#     :param obj:
#     :param newData:
#     :param INCLUDES:
#     :param EXCLUDES:
#     :return:
#     """
#     result = {}
#     for k, v in newData.items():
#         if INCLUDES and k not in INCLUDES:
#             continue
#         if EXCLUDES and k in EXCLUDES:
#             continue
#         if hasattr(obj, k):
#             auxObjV = getattr(obj, k)
#             objV = auxObjV.get() if isinstance(auxObjV, LoggedValue) else auxObjV
#             if v != objV:
#                 result[k] = (objV, v)
#     return result

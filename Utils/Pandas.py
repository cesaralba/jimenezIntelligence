'''
Created on Mar 31, 2018

@author: calba
'''


def combinaPDindexes(indexData, sep="-"):
    newNames = [sep.join(x).rstrip(sep) for x in indexData.values]
    return newNames


def NumberToLetters(q):
    aux = q
    result = ''
    while aux >= 0:
        remain = aux % 26
        result = chr(remain + 65) + result
        aux = (aux // 26) - 1
    return result


def AllCells(sheet, offsetColumnas=0, offsetFilas=0):
    result = (f"{NumberToLetters(sheet.dim_colmin + offsetColumnas)}"
              f"{sheet.dim_rowmin + offsetFilas + 1}"
              ":"
              f"{NumberToLetters(sheet.dim_colmax)}{sheet.dim_rowmax + 1}")

    return result

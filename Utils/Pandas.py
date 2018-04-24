'''
Created on Mar 31, 2018

@author: calba
'''


def combinaPDindexes(indexData, sep="-"):

    newNames = [sep.join(x).rstrip(sep) for x in indexData.values]
    return newNames


def NumberToLetters(q):
    q = q
    result = ''
    while q >= 0:
        remain = q % 26
        result = chr(remain + 65) + result
        q = (q // 26) - 1
    return result


def AllCells(sheet, offsetColumnas=0, offsetFilas=0):

    result = "%s%i:%s%i" % (NumberToLetters(sheet.dim_colmin + offsetColumnas), sheet.dim_rowmin + offsetFilas + 1,
                            NumberToLetters(sheet.dim_colmax), sheet.dim_rowmax + 1)
    return result

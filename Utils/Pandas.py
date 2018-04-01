'''
Created on Mar 31, 2018

@author: calba
'''


def combinaPDindexes(indexData, sep="-"):

    newNames = [sep.join(x).rstrip(sep) for x in indexData.values]
    return newNames

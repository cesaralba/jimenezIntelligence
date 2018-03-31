'''
Created on Mar 31, 2018

@author: calba
'''


def combinaPDindexes(indexData, sep="-"):

    result = [sep.join([y for y in x if y != ""]) for x in list(indexData)]

    return result

"""
Parser, compiler and runtime support for My-files.
"""
from __future__ import absolute_import


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


from _compat import *


def my_compile(source, filename='<unknown>', mode='exec'):
    try:
        from mylang.parse import parse
    except ImportError:
        raise ImportError('PLY is not installed')

    ast_root = parse(source, filename, mode)
    return compile(ast_root, filename, mode)


def my_exec(code, globals):
    from mylang.runtime import builtins
    my_globals = DelegatingDict(globals,
                                __builtins__=builtins,
                                __my_module__=DictObject(globals))
    exec(code, my_globals)


class DictObject(object):
    def __init__(self, dict_):
        super(DictObject, self).__init__()
        self.__dict__ = dict_


class DelegatingDict(dict):
    __slots__ = 'dict_'

    def __init__(self, dict_, **kwargs):
        super(DelegatingDict, self).__init__(**kwargs)
        self.dict_ = dict_

    def __missing__(self, key):
        return self.dict_[key]




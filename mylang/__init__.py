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



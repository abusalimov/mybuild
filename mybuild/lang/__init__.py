"""Parser, compiler and runtime support for Mybuild DSL.

The parser is based on the PLY parser engine; it translates the input source
into a Python AST (abstract syntax tree) which, in turn, is then compiled and
executed as a regular Python code.
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


def my_compile(source, filename='<unknown>', mode='exec'):
    try:
        from mylang.parse import my_parse
    except ImportError:
        raise ImportError('PLY is not installed')

    ast_root = my_parse(source, filename, mode)
    return compile(ast_root, filename, mode)



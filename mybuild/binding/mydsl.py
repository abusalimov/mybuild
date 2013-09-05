"""
Bindings for Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


from _compat import *

import functools

from mybuild import core
from mybuild.binding import pydsl
from util.deco import class_from_constructor


class MyDslModuleMeta(pydsl.PyDslModuleMeta):
    __my_new__ = class_from_constructor


class MyDslModule(extend(pydsl.PyDslModule,
                         metaclass=MyDslModuleMeta, internal=True)):
    pass


module = MyDslModule
option = core.Optype


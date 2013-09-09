"""
Bindings for Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'project', 'option']


from _compat import *

import functools

from mybuild import core
from mybuild.binding import pydsl
from util.deco import class_from_constructor


class MyDslModuleMeta(pydsl.PyDslModuleMeta):
    __my_new__ = class_from_constructor


class MyDslModuleBase(extend(pydsl.PyDslModuleBase,
                             metaclass=MyDslModuleMeta, internal=True)):
    pass


module  = core.new_module_type('MyDslModule',  MyDslModuleBase, core.Module)
project = core.new_module_type('MyDslProject', MyDslModuleBase, core.Project)

option = core.Optype


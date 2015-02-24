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


class MyDslModuleMeta(core.ModuleMeta):

    def _prepare_optypes(cls):
        return []

class MyDslApplicationMeta(core.ModuleMeta):

    def _prepare_optypes(cls):
        return []

class MyDslModuleBase(extend(core.Module,
                             metaclass=MyDslModuleMeta, internal=True)):
    pass

class MyDslApplicationBase(extend(core.Application,
                             metaclass=MyDslApplicationMeta, internal=True)):
    pass

MyDslModuleMeta._base_type = MyDslModuleBase
MyDslApplicationMeta._base_type = MyDslApplicationBase


module  = MyDslModuleMeta
application  = MyDslApplicationMeta

project = None

option = core.Optype


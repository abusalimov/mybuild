"""
Extends the standard operator module with few handy functions.
"""
from __future__ import absolute_import

from operator import *
from functools import partial as _partial

from util.compat import *


class GetterType(object):
    """
    getter.attr  -> attrgetter('attr')
    getter[item] -> itemgetter(item)
    """

    def __getattr__(self, attr):
        return attrgetter(attr)

    def __getitem__(self, item):
        return itemgetter(item)

getter = GetterType()


class InvokerType(object):
    """
    invoker.meth(*args, **kwargs) -> methodcaller('meth', *args, **kwargs)
    """

    def __getattr__(self, meth):
        return _partial(methodcaller, meth)

invoker = InvokerType()


def instanceof(classinfo):
    return lambda obj: isinstance(obj, classinfo)
def subclassof(classinfo):
    return lambda obj: issubclass(obj, classinfo)



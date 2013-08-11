"""
Necessary bindings for Pybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'option']


import functools
import inspect
import threading
from operator import attrgetter

from mybuild.core import ModuleType
from mybuild.core import Module
from mybuild.core import Optype

from util.misc import constructor_decorator
from util.compat import *


class PyFileModuleType(ModuleType):
    """
    Infers options from class constructor. To cancel such behavior, provide a
    keyword argument intermediate=True.
    """

    def __init__(cls, name, bases, attrs, intermediate=False):
        super(PyFileModuleType, cls).__init__(name, bases, attrs,
                optypes=cls._init_to_options() if not intermediate else None)

    def _init_to_options(cls):
        """Converts a constructor argspec into a list of Option objects."""

        try:
            func = cls.__dict__['__init__']  # to avoid MRO lookup
        except KeyError:
            return []

        if isinstance(func, type(object.__init__)):
            # wrapper descriptor, give up
            return []

        args, va, kw, defaults = inspect.getargspec(inspect.unwrap(func))
        defaults = defaults or ()

        if va is not None:
            raise TypeError(
                'Arbitrary arguments are not supported: *%s' % va)
        if kw is not None:
            raise TypeError(
                'Arbitrary keyword arguments are not supported: **%s' % kw)

        if not args:
            raise TypeError(
                'Module function must accept at least one argument')
        if len(args) == len(defaults):
            raise TypeError(
                'The first argument cannot have a default value: %s' % args[0])

        option_args = args[1:]
        for arg in option_args:
            if not isinstance(arg, basestring):
                raise TypeError(
                    'Tuple parameter unpacking is not supported: %s' % arg)

        head = [Optype() for _ in range(len(option_args) - len(defaults))]
        tail = [optype if isinstance(optype, Optype) else Optype(optype)
                for optype in defaults]

        return [optype.set(name=name)
                for optype, name in zip(head + tail, option_args)]


class PyFileModule(with_meta(PyFileModuleType, intermediate=True), Module):

    def _consider(self, expr):
        self._context.consider(expr, origin=self)

    def _constrain(self, expr):
        self._context.constrain(expr, origin=self)

    def __repr__(self):
        return repr(self._optuple)

    # XXX
    constrain = _constrain
    consider  = _consider


module = constructor_decorator(PyFileModule, __doc__=
    """
    Example of a simple module without any options:

    >>> @module
    ... def modname(self):
    ...     pass

    More examples:

    >>> @module
    ... def m(self,
    ...       foo = option(0, 'one', 'two'),    # one of these, or any other
    ...       bar = option.enum(38400, 115200), # enumeration of two values
    ...       baz = option.bool(default=True),  # boolean flag
    ...         ):
    ...     pass

    >>> class modclass(module):
    ...     def __init__(self, opt = option.bool()):
    ...         pass

    """)

option = Optype

if __name__ == '__main__':
    import doctest
    doctest.testmod()


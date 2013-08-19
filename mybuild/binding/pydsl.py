"""
Necessary bindings for Pybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'option']


from _compat import *

import inspect

from mybuild.core import ModuleMeta
from mybuild.core import Module
from mybuild.core import Optype

from util.deco import constructor_decorator


class PyFileModuleMeta(ModuleMeta):
    """Infers options from class constructor."""

    def _create_optypes(cls):
        """Converts a constructor argspec into a list of Optype objects."""
        try:
            func = cls.__dict__['__init__']  # to avoid MRO lookup
        except KeyError:
            return []

        if isinstance(func, type(object.__init__)):
            # wrapper descriptor, give up
            return []

        args, va, kw, dfls = inspect.getargspec(inspect.unwrap(func))
        dfls = dfls or []

        if not args and not va:
            raise TypeError('Module must accept at least one argument')

        for arg in args:
            if not isinstance(arg, basestring):
                raise TypeError('Tuple parameter unpacking '
                                'is not supported: {arg}'.format(**locals()))

        if args:   # forget about the first arg (which is usually 'self')
            if len(args) == len(dfls):
                del dfls[0]
            del args[0]

        head = [Optype() for _ in range(len(args) - len(dfls))]
        tail = [optype if isinstance(optype, Optype) else Optype(optype)
                for optype in dfls]

        return [optype.set(name=name)
                for optype, name in zip(head + tail, args)]


class PyFileModule(extend(Module, metaclass=PyFileModuleMeta, internal=True)):
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

    """

    def _consider(self, expr):
        self._context.consider(expr, origin=self)

    def _constrain(self, expr):
        self._context.constrain(expr, origin=self)

    def __repr__(self):
        return repr(self._optuple)

    # XXX
    constrain = _constrain
    consider  = _consider


module = constructor_decorator(PyFileModule)
option = Optype

if __name__ == '__main__':
    import doctest
    doctest.testmod()


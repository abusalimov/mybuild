"""
Necessary bindings for Pybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'option']


from _compat import *

import inspect

from mybuild import core
from util.deco import constructor_decorator


class PyDslModuleMeta(core.ModuleMeta):
    """Infers options from class constructor."""

    def __init__(cls, name, bases, attrs, internal=False):
        super(PyDslModuleMeta, cls).__init__(name, bases, attrs,
                optypes=(None if internal else
                         cls._optypes_from_constructor()))

    def _optypes_from_constructor(cls):
        """Converts a constructor argspec into a list of Optype objects."""
        func = cls.__dict__.get('__init__')  # to avoid MRO lookup

        if func is None or isinstance(func, type(object.__init__)):
            # no constructor, or it is a wrapper descriptor, give up
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

        def to_optype(optype_or_default):
            if isinstance(optype_or_default, core.Optype):
                return optype_or_default
            return core.Optype(optype_or_default)

        head = [core.Optype() for _ in range(len(args) - len(dfls))]
        tail = list(map(to_optype, dfls))

        return [optype.set(name=name)
                for optype, name in zip(head + tail, args)]

    def _instantiate(cls, optuple, *args, **kwargs):
        instance = cls.__new__(cls, optuple, *args, **kwargs)

        if isinstance(instance, cls):
            # The following dirty hack is to be sure that Module.__init__ gets
            # called with proper arguments and exactly once.
            super(PyDslModule, instance).__init__(optuple, *args, **kwargs)
            # On the other hand, the real __init__ is invoked with keyword
            # arguments holding option values and it is not required to call
            # super constructor (which anyway does nothing, see
            # PyDslModule.__init__).
            instance.__init__(**optuple._asdict())

        return instance


class PyDslModule(extend(core.Module,
                         metaclass=PyDslModuleMeta, internal=True)):
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

    def __init__(_self, *args, **kwargs):
        # Notice the absence of super constructor call,
        # see PyDslModuleMeta._instantiate for explanations.
        pass

    def __repr__(self):
        return repr(self._optuple)

    # XXX
    constrain = core.Module._constrain
    consider  = _consider  = core.Module._discover


module = constructor_decorator(PyDslModule)
option = core.Optype


if __name__ == '__main__':
    import doctest
    doctest.testmod()


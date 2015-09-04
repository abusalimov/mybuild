"""
Necessary bindings for Pybuild files.
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *

import inspect

from mybuild import core
from mybuild.util.deco import constructor_decorator


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'project', 'option']


class PyDslModuleMeta(core.ModuleMetaBase):
    """Infers options from class constructor.

    Adds an optional 'internal' keyword argument.

    Produces real modules by default, however subclasses must still pass
    an 'option_types' keyword argument or provide a resonable implementation
    of '_prepare_optypes' method.
    """

    def __init__(cls, name, bases, attrs, internal=False, **kwargs):
        """Keyword arguments are passed to '_prepare_optypes' method."""
        super(PyDslModuleMeta, cls).__init__(name, bases, attrs,
                option_types=(None if internal else
                              cls._prepare_optypes(**kwargs)))

    def _prepare_optypes(cls):
        """Converts a constructor argspec into a list of Optype objects."""
        func = cls.__dict__.get('__init__')  # to avoid MRO lookup
        try:
            argspec = inspect.getargspec(inspect.unwrap(func))
        except TypeError:  # no constructor, or it is a wrapper descriptor
            return []
        else:
            args, va, kw, dfls = argspec
            dfls = dfls or []

        if not args and not va:
            raise TypeError('Module must accept at least one argument')

        for arg in args:
            if not isinstance(arg, str):
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

        return [(name, optype.set(name=name))
                for name, optype in zip(args, head + tail)]

    def _instantiate(cls, optuple, *args, **kwargs):
        instance = cls.__new__(cls, optuple, *args, **kwargs)

        if isinstance(instance, cls):
            # The following dirty hack is to be sure that Module.__init__ gets
            # called with proper arguments and exactly once.
            super(PyDslModuleBase, instance).__init__(optuple, *args, **kwargs)
            # On the other hand, the real __init__ is invoked with keyword
            # arguments holding option values and it is not required to call
            # super constructor (which anyway does nothing, see
            # PyDslModule.__init__).
            instance.__init__(**optuple._asdict())

        return instance


class PyDslModuleBase(extend(core.ModuleBase,
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

    >>> list(m._options)
    ['foo', 'bar', 'baz']

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


def new_module_type(name, *bases):
    return new_type(name, bases, {}, metaclass=core.ModuleMetaBase, internal=True)


module  = constructor_decorator(new_module_type('PyDslModule',
                                PyDslModuleBase, core.Module))
project = constructor_decorator(new_module_type('PyDslProject',
                                PyDslModuleBase, core.Project))

application = None
library = None

option = core.Optype


if __name__ == '__main__':
    import doctest
    doctest.testmod()

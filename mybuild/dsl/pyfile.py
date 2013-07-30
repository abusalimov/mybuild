"""
Necessary bindings for Pybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'option']


import functools
import inspect

from ..core import Module
from ..core import Option

from nsloader import pyfile

from util.compat import *


PYFILE_DEFAULTS = [
    "module",
    "option",
]


class MybuildPyFileLoader(pyfile.PyFileLoader):

    MODULE   = 'PYBUILD'
    FILENAME = 'Pybuild'

    @classmethod
    def init_ctx(cls, ctx, initials=None):
        if initials is None:
            initials = {}

        builtins = dict(initials)
        globals_ = globals()

        for var in PYFILE_DEFAULTS:
            builtins.setdefault(var, globals_[var])  # initials take precedence

        return super(MybuildPyFileLoader, cls).init_ctx(ctx, builtins)


class PybuildModule(Module):

    def __init__(self, instance_type):
        if not inspect.isclass(instance_type):
            raise TypeError("Expected a class, got '%s' object instead" %
                            type(instance_type).__name__)

        super(PybuildModule, self).__init__(instance_type,
                self._ctor_to_options(instance_type))

    @classmethod
    def _from_func(cls, func):
        # For unknown reasons __doc__ attribute of type objects is read-only,
        # and update_wrapper is unable to set it. The same is about __dict__
        # attribute which becomes a dictproxy upon class definition,
        # not a dict.
        #
        # So instead we create a new type manually.

        type_dict = dict(func.__dict__,
                         __module__ = func.__module__,
                         __doc__ = func.__doc__,
                         __init__ = func)

        return cls(type(func.__name__, (object,), type_dict))

    @classmethod
    def _ctor_to_options(cls, instance_type):
        """Converts a constructor argspec into a list of Option objects."""

        func = instance_type.__init__
        if isinstance(func, type(object.__init__)):
            # wrapper descriptor, give up
            return []

        args, va, kw, defaults = inspect.getargspec(func)
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

        head = [Option() for _ in range(len(option_args) - len(defaults))]
        tail = [option if isinstance(option, Option) else Option(option)
                for option in defaults]

        return [option.set(name=name)
                for option, name in zip(head + tail, option_args)]


def module(func_or_class):
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

    """
    if inspect.isfunction(func_or_class):
        ret = PybuildModule._from_func(func_or_class)
    else:
        ret = PybuildModule(func_or_class)
    return functools.update_wrapper(ret, func_or_class)


option = Option


if __name__ == '__main__':
    import doctest
    doctest.testmod()


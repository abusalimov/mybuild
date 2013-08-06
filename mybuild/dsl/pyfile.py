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

from . import with_defaults
from ..core import ModuleType
from ..core import Module
from ..core import Optype

from nsloader import pyfile

from util import constructor_decorator
from util.compat import *


PYFILE_DEFAULTS = ['module', 'option']


class MybuildPyFileLoader(pyfile.PyFileLoader):

    MODULE   = 'PYBUILD'
    FILENAME = 'Pybuild'

    @classmethod
    def init_ctx(cls, ctx, initials=None):
        return super(MybuildPyFileLoader, cls).init_ctx(ctx,
                with_defaults(initials, PYFILE_DEFAULTS, globals()))


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

        head = [Optype() for _ in range(len(option_args) - len(defaults))]
        tail = [optype if isinstance(optype, Optype) else Optype(optype)
                for optype in defaults]

        return [optype.set(name=name)
                for optype, name in zip(head + tail, option_args)]


class PyFileModule(with_metaclass(PyFileModuleType, intermediate=True), Module):

    def _consider(self, expr):
        self._context.consider(expr, self)

    def _constrain(self, expr):
        self._context.constrain(expr, self)

    def __repr__(self):
        return repr(self._optuple)

    def build(self, bld):
        src = getattr(self, 'sources', [])
        bld(features='mylink', source=src, target='test')
        print('+++++++++ add task ++++')
        print('module = ' + str(self))
        print('sources = ' + str(src))
        print('+++++++++++++++++++++++')


try:
    from waflib.Task import Task
    from waflib.TaskGen import feature, extension, after_method
    from waflib.Tools import ccroot

    @after_method('process_source')
    @feature('mylink')
    def call_apply_link(self):
        print('linking' + str(self))

    class mylink(ccroot.link_task):
        run_str = 'cat ${SRC} > ${TGT}'

    class ext2o(Task):
        run_str = 'cp ${SRC} ${TGT}'

    @extension('.c')
    def process_ext(self, node):
        self.create_compiled_task('ext2o', node)

except ImportError:
    pass  # XXX move Waf-related stuff from here


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


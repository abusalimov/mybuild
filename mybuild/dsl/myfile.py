"""
Bindings for Mybuild files.
"""
from __future__ import absolute_import

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


import functools

from . import with_defaults
from ..core import Module
from ..core import Option

from nsloader import myfile
from myfile.linkage import MyfileObjectProxy

from util.compat import *


MYFILE_DEFAULTS = ['module', 'option']


class MybuildMyFileLoader(myfile.MyFileLoader):

    MODULE   = 'MYBUILD'
    FILENAME = 'Mybuild'

    @classmethod
    def init_ctx(cls, ctx, initials=None):
        return super(MybuildMyFileLoader, cls).init_ctx(ctx,
                with_defaults(initials, MYFILE_DEFAULTS, globals()))


class MyFileModule(Module):

    class Proxy(MyfileObjectProxy):
        slots = 'cls'

        def __init__(self, cls, stub):
            super(MyFileModule.Proxy, self).__init__(stub)
            self.cls = cls

        def __call__(self, *args, **kwargs):
            type_dict = dict(__module__ = self.stub.linker.module,
                             __doc__    = self.stub.docstring)
            type_name = self.stub.name or '<noname>'
            return self.cls(type(type_name, (object,), type_dict),
                            self.cls._args_kwargs_to_options(args, kwargs))

    @classmethod
    def my_proxy(cls, stub):
        return cls.Proxy(cls, stub)

    @classmethod
    def _args_kwargs_to_options(cls, arg_options, kwarg_options):
        """Converts args/kwargs into a list of options."""

        for option in arg_options:
            if not isinstance(option, Option):
                raise TypeError(
                    'Positional argument must be an option: %s' % option)
            if not hasattr(option, '_name'):
                raise TypeError(
                    'Positional option must provide a name explicitly')

        options = list(arg_options)

        for name, option in iteritems(kwarg_options):
            if not isinstance(option, Option):
                option = Option(option)
            if not hasattr(option, '_name'):
                option.set(name=name)

            options.append(option)

        return options


module = MyFileModule
option = Option

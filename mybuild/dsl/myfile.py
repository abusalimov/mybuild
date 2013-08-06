"""
Bindings for Mybuild files.
"""
from __future__ import absolute_import

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


import functools

from . import with_defaults
from ..core import ModuleType
from ..core import Module
from ..core import Optype

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


class MyFileModuleType(ModuleType):

    class Proxy(MyfileObjectProxy):
        slots = 'mcls'

        def __init__(self, mcls, stub):
            super(MyFileModule.Proxy, self).__init__(stub)
            self.mcls = mcls

        def __call__(self, *args, **kwargs):
            type_dict = dict(__module__ = self.stub.linker.module,
                             __doc__    = self.stub.docstring)
            type_name = self.stub.name or '<noname>'
            return self.mcls(type_name, (MyFileModule,), type_dict,
                             self.mcls._args_kwargs_to_options(args, kwargs))

    @classmethod
    def my_proxy(mcls, stub):
        return mcls.Proxy(mcls, stub)

    @classmethod
    def _args_kwargs_to_options(mcls, arg_options, kwarg_options):
        """Converts args/kwargs into a list of options."""

        for optype in arg_options:
            if not isinstance(optype, Optype):
                raise TypeError(
                    'Positional argument must be an option: %s' % optype)
            if not hasattr(optype, '_name'):
                raise TypeError(
                    'Positional option must provide a name explicitly')

        options = list(arg_options)

        for name, optype in iteritems(kwarg_options):
            if not isinstance(optype, Optype):
                optype = Optype(optype)
            if not hasattr(optype, '_name'):
                optype.set(name=name)

            options.append(optype)

        return options


class MyFileModule(with_meta(MyFileModuleType), Module):
    """docstring for MyFileModule"""

    def __init__(self, domain, instance_node):
        super(MyFileModule, self).__init__()


module = MyFileModuleType
option = Optype

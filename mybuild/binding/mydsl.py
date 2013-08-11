"""
Bindings for Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


from _compat import *

from mybuild.core import ModuleType
from mybuild.core import Module
from mybuild.core import Optype

from mylang.linkage import MyfileObjectProxy


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

    def __init__(_self, **kwargs):
        super(Module, _self).__init__()
        # TODO NIY
        print type(_self), _self


module = MyFileModuleType
option = Optype

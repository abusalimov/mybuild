"""
Bindings for Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


from _compat import *

import functools

from mybuild import core
from util.deco import constructor_decorator
from util.prop import class_instance_method


class MyDslModuleTypeStub(object):
    """Stub for a Module type which is converted into a real type upon
    a call to __my_new__."""

    _module_bases = [core.Module]

    def __init__(self, *args, **kwargs):
        """Args/kwargs are converted into a list of options."""
        super(MyDslModuleTypeStub, self).__init__()

        for optype in args:
            if not isinstance(optype, core.Optype):
                raise TypeError('Positional argument must be an option: '
                                '{optype}'.format(**locals()))
            if not hasattr(optype, '_name'):
                raise TypeError('Positional option must provide a name '
                                'explicitly')

        optypes = list(args)

        for name, optype in iteritems(kwargs):
            if not isinstance(optype, core.Optype):
                optype = core.Optype(optype)
            if not hasattr(optype, '_name'):
                optype.set(name=name)

            optypes.append(optype)

        self.optypes = optypes

    @class_instance_method
    def __my_new__(cls, self, init_func):
        if self is None:
            # let 'module() {...}' and 'module {...}' to behave the same way
            return cls().__my_new__(init_func)

        @functools.wraps(init_func)
        def module(self, *args, **kwargs):
            init_func(self)

        return self._module_from_constructor(module)

    @property
    def _module_from_constructor(self):
        return constructor_decorator(*self._module_bases, optypes=self.optypes)


module = MyDslModuleTypeStub
option = core.Optype


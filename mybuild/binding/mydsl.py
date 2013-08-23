"""
Bindings for Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = ['module', 'option']


from _compat import *

from mybuild.core import ModuleMeta
from mybuild.core import Module
from mybuild.core import Optype

from util.prop import class_instance_method


class ModuleTypeStub(object):
    """Stub for a Module type is converted into a real type upon a call to
    __my_prepare_obj__."""

    def __init__(self, *args, **kwargs):
        super(ModuleTypeStub, self).__init__()
        self.optypes = self._create_optypes(*args, **kwargs)

    @classmethod
    def _create_optypes(cls, *args, **kwargs):
        """Args/kwargs are converted into a list of options."""

        for optype in args:
            if not isinstance(optype, Optype):
                raise TypeError('Positional argument must be an option: '
                                '{optype}'.format(**locals()))
            if not hasattr(optype, '_name'):
                raise TypeError('Positional option must provide a name '
                                'explicitly')

        optypes = list(args)

        for name, optype in iteritems(kwargs):
            if not isinstance(optype, Optype):
                optype = Optype(optype)
            if not hasattr(optype, '_name'):
                optype.set(name=name)

            optypes.append(optype)

        return optypes

    @class_instance_method
    def __my_prepare_obj__(cls, self, py_module, names):
        if self is None:
            # to let 'module() {}' and 'module {}' behave the same.
            return cls()._my_prepare_obj__(py_module, name)

        if names:
            name = names[0]
        else:
            name = '<unnamed>'
        type_dict = dict(__module__=py_module)

        return (new_type(name, (Module,), type_dict,
                         metaclass=ModuleMeta, optypes=self.optypes),
                True)  # and yes, proxify it


module = ModuleTypeStub
option = Optype


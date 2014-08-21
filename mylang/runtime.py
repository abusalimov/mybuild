"""
Runtime support for My-lang.
"""
from __future__ import print_function


__author__ = "Eldar Abusalimov"
__date__ = "2013-08-22"


from _compat import *
from _compat import _calculate_meta

from util.prop import cached_property
from util.prop import cached_class_property


builtin_names = [
    # Functions
    'abs',        'all',        'any',        'bin',
    'bool',       'dict',       'filter',     'float',
    'format',     'getattr',    'hasattr',    'hex',
    'id',         'int',        'isinstance', 'issubclass',
    'iter',       'len',        'list',       'map',
    'max',        'min',        'object',     'pow',
    'print',      'range',      'repr',       'reversed',
    'set',        'slice',      'sorted',     'str',
    'sum',        'tuple',      'type',       'zip',

    # Constants
    'False', 'True', 'None',

    # Mylang-specific
    '__my_new_type__',
    '__my_call_args__',
    '__my_exec_module__',

    # Disabled Python builtins:
    #
    # basestring bytearray callable chr classmethod compile complex delattr
    # dir divmod enumerate eval execfile file frozenset globals hash help input
    # locals long memoryview next oct open ord property raw_input reduce reload
    # round setattr staticmethod super unichr unicode vars xrange __import__
    # apply buffer coerce intern
]

class __my_exec_module__(Exception):

    def __init__(self, trampoline):
        super(__my_exec_module__, self).__init__()
        trampoline(self)
        raise self

    def __call__(self, bindings):
        for name, _, func in bindings:
            if '.' in name:
                raise NotImplementedError
            func.__name__ = name
            yield func()

def __my_call_args__(*args, **kwargs):
    return args, kwargs


# Provide a similar to PEP 3115 mechanism for class creation
def my_new_type(meta, name,
                module=None, docstring=None,
                property_bindings=[], default_binding_func=None,
                bases=(), kwds={}):
    """Create a class object dynamically using the appropriate metaclass."""
    meta, ns = my_prepare_type(meta, name, bases, kwds)

    if module is not None:
        ns.setdefault('__module__', module)
    if docstring is not None:
        ns.setdefault('__doc__', docstring)

    delegate = my_ns_delegate(meta, ns)
    my_exec_body(ns, delegate, property_bindings, default_binding_func)

    return meta(name, bases, ns, **kwds)

__my_new_type__ = my_new_type


def my_exec_body(ns, delegate, props=[], dfl_func=None):
    for name, static, func in props:
        func.__name__ = name
        ns[name] = delegate.create_property_binding(name, static, func)

    if dfl_func is not None:
        dfl_name = delegate.default_binding_name
        dfl_func.__name__ = dfl_name
        ns[dfl_name] = delegate.create_default_binding(dfl_func)


def my_prepare_type(meta, name, bases=(), kwds={}):
    """Call the __prepare__ method of the appropriate metaclass.

    Returns (metaclass, namespace) as a tuple

    *metaclass* is the appropriate metaclass
    *namespace* is the prepared class namespace
    """
    if isinstance(meta, type):
        # when meta is a type, we first determine the most-derived metaclass
        # instead of invoking the initial candidate directly
        meta = _calculate_meta(meta, bases)

    if hasattr(meta, '__prepare__'):
        ns = meta.__prepare__(name, bases, **kwds)
    else:
        ns = {}

    return meta, ns


class MyDelegate(object):
    __slots__ = ()

    def __init__(self, ns):
        super(MyDelegate, self).__init__()

    default_binding_name = 'return'

    def create_property_binding(self, name, static, func):
        if static:
            return cached_class_property(func, attr=name)
        else:
            return cached_property(func, attr=name)

    def create_default_binding(self, func):
        return cached_class_property(func, attr=self.default_binding_name)


def my_ns_delegate(meta, ns):
    """Call the __my_delegate__ method (if any) of the metaclass."""
    delegate_type = getattr(meta, '__my_delegate__', MyDelegate)
    return delegate_type(ns)


# Note that some name are taken from globals of this module (this includes
# _compat.* as well), and the rest come from Python builtins.
builtins = dict((name, eval(name)) for name in builtin_names)


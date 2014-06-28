"""
Runtime support for My-lang.
"""
from __future__ import print_function


__author__ = "Eldar Abusalimov"
__date__ = "2013-08-22"


from _compat import *
from _compat import _calculate_meta


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

    # Disabled Python builtins:
    #
    # basestring bytearray callable chr classmethod compile complex delattr
    # dir divmod enumerate eval execfile file frozenset globals hash help input
    # locals long memoryview next oct open ord property raw_input reduce reload
    # round setattr staticmethod super unichr unicode vars xrange __import__
    # apply buffer coerce intern
]


def __my_call_args__(*args, **kwargs):
    return args, kwargs

def __my_new_type__(exec_body, meta=None, name='_', bases=(), kwds={}):
    if meta is not None:
        return my_new_type(exec_body, meta, name, bases, kwds)

    else: # module scope
        exec_body()


class MyDelegate(object):

    def __init__(self, ns):
        super(MyDelegate, self).__init__()
        super(MyDelegate, self).__setattr__('__dict__', ns)

    def __setattr__(self, name, func):
        super(MyDelegate, self).__setattr__(name, self.func_to_value(func))

    func_to_value = staticmethod(property)


# Provide a PEP 3115 compliant mechanism for class creation
def my_new_type(exec_body, meta, name, bases=(), kwds={}):
    """Create a class object dynamically using the appropriate metaclass."""
    meta, ns = my_prepare_type(meta, name, bases, kwds)
    ns.setdefault('__module__', exec_body.__module__)

    delegate = my_ns_delegate(meta, ns)
    exec_body(delegate)

    return meta(name, bases, ns, **kwds)


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

def my_ns_delegate(meta, ns):
    """Call the __my_delegate__ method (if any) of the metaclass."""
    delegate_type = getattr(meta, '__my_delegate__', MyDelegate)
    return delegate_type(ns)


def __objtype_new_meth(objtype):
    try:
        return objtype.__my_new__
    except AttributeError:
        raise TypeError("'{cls}' objects cannot be used in "
                        "'object {{...}}' expression "
                        "(missing '__my_new__' method)"
                        .format(cls=type(objtype)))


# Note that some name are taken from globals of this module (this includes
# _compat.* as well), and the rest come from Python builtins.
builtins = dict((name, eval(name)) for name in builtin_names)


"""
Runtime support for My-lang.
"""
from __future__ import print_function


__author__ = "Eldar Abusalimov"
__date__ = "2013-08-22"


from _compat import *


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
    '__my_objdef__',
    '__my_xobjdef__',

    # Disabled Python builtins:
    #
    # basestring bytearray callable chr classmethod compile complex delattr
    # dir divmod enumerate eval execfile file frozenset globals hash help input
    # locals long memoryview next oct open ord property raw_input reduce reload
    # round setattr staticmethod super unichr unicode vars xrange __import__
    # apply buffer coerce intern
]


def __objtype_new_meth(objtype):
    try:
        return objtype.__my_new__
    except AttributeError:
        raise TypeError("'{cls}' objects cannot be used in "
                        "'object {{...}}' expression "
                        "(missing '__my_new__' method)"
                        .format(cls=type(obj)))

def __fixup_name(closure, name):
    closure.__name__ = name
    return closure


def __my_objdef__(objtype, name, closure_maker, *args):
    """
    Mylang source:
        objtype foo {...};

    Python equivalent:
        def __my_closure__():
            def closure():
                ...
            return closure
        __my_objdef__(objtype, 'foo', __my_closure__)

    Runtime:
        closure = __my_closure__()
        closure.__name__ = name
        objtype.__my_new__(closure)
    """
    objtype_new = __objtype_new_meth(objtype)
    return objtype_new(__fixup_name(closure_maker(*args), name))

def __my_xobjdef__(objtype, names, closure_maker, *args):
    """
    Mylang source:
        objtype foo: bar = {...};

    Python equivalent:
        def __my_closure__():
            def closure():
                ...
            return closure
        self.foo, bar = __my_xobjdef__(objtype, ['foo', 'bar'], __my_closure__)
    """
    objtype_new = __objtype_new_meth(objtype)
    return [objtype_new(__fixup_name(closure_maker(*args), name))
            for name in names]


# Note that some name are taken from globals of this module (this includes
# _compat.* as well), and the rest come from Python builtins.
builtins = dict((name, eval(name)) for name in builtin_names)


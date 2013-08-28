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
    '__my_set_block__',
    '__my_new_block__',

    # Disabled Python builtins:
    #
    # basestring bytearray callable chr classmethod compile complex delattr
    # dir divmod enumerate eval execfile file frozenset globals hash help input
    # locals long memoryview next oct open ord property raw_input reduce reload
    # round setattr staticmethod super unichr unicode vars xrange __import__
    # apply buffer coerce intern
]


def __my_new_block__(obj, func, **attrs):
    """
    Source:
        name :: obj {...}
    AST:
        name = __my_new_block__(obj, lambda: ...,
                                __module__=__name__,
                                __doc__='docstring',
                                __name__='name')
    Runtime:
        obj.__my_new__(init_func)
    """
    attrs.setdefault('__module__', func.__module__)
    attrs.setdefault('__doc__')
    attrs.setdefault('__name__', '<unnamed>')

    try:
        obj_new = obj.__my_new__
    except AttributeError:
        raise TypeError("'{cls}' objects cannot be used in "
                        "'object {{...}}' expression "
                        "(missing '__my_new__' method)"
                        .format(cls=type(obj)))

    def init_func(obj, getter_obj=None):
        if getter_obj is None:
            getter_obj = obj
        return _exec_setters(func(obj, getter_obj))

    for attr in iteritems(attrs):
        setattr(init_func, *attr)

    return obj_new(init_func)


def __my_set_block__(obj, func):
    """
    Source:
        obj.{...}
    AST:
        __my_set_block__(obj, lambda: ...)
    """
    return _exec_setters(func(obj, obj))


def _exec_setters(setters):
    """
    Source:
        ... {attr: value, items[42]: self.prop}
    AST:
        ... lambda __my_self__, self: [
                (__my_self__,      'attr', 1, value),
                (__my_self__.items, 42,    0, self.prop),
            ]
    """
    for obj, target, is_attr, value in setters:
        if is_attr:
            setattr(obj, target, value)
        else:
            obj[target] = value

    return obj


# Note that some name are taken from globals of this module (this includes
# _compat.* as well), and the rest come from Python builtins.
builtins = dict((name, eval(name)) for name in builtin_names)


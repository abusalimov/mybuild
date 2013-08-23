"""
Runtime support for My-lang.
"""
from __future__ import print_function


__author__ = "Eldar Abusalimov"
__date__ = "2013-08-22"


from _compat import *

import inspect

from mylang import proxy
from util.itertools import pop_iter


builtin_names = [
    'abs',        'all',        'any',        'bin',
    'bool',       'cmp',        'dict',       'filter',
    'float',      'format',     'getattr',    'hasattr',
    'hex',        'id',         'int',        'isinstance',
    'issubclass', 'iter',       'len',        'list',
    'map',        'max',        'min',        'object',
    'pow',        'print',      'range',      'repr',
    'reversed',   'set',        'slice',      'sorted',
    'str',        'sum',        'tuple',      'type',
    'zip',

    'False', 'True', 'None',
]

# Disabled builtins:
#
# basestring bytearray callable chr classmethod compile complex delattr
# dir divmod enumerate eval execfile file frozenset globals hash help input
# locals long memoryview next oct open ord property raw_input reduce reload
# round setattr staticmethod super unichr unicode vars xrange __import__
# apply buffer coerce intern

# Note that some name are taken from globals of this module (this includes
# _compat.* as well), and the rest come from Python builtins.
default_builtins = dict((name, eval(name)) for name in builtin_names)


def prepare_builtins(ctx=None):
    if ctx is None:
        ctx = ExecContext()

    return dict(default_builtins,
                __my_setter__=ctx.setter)


class ExecContext(object):
    """Provides minimal runtime support."""

    def prepare_obj(self, obj, func, names):
        func_globals = func.__globals__ if py3k else func.func_globals

        try:
            module = func_globals['__name__']
        except KeyError:
            raise NameError("name '__name__' is not defined")

        # (obj) and (obj {}) are not always the same
        prepare_func = getattr(obj, '__my_prepare_obj__', None)

        if prepare_func is not None:
            return prepare_func(module, names)
        else:
            return obj, False

    @classmethod
    def exec_setter(cls, obj, func):
        for obj, target, is_attr, value in func(obj):
            if is_attr:
                setattr(obj, target, value)
            else:
                obj[target] = value

    def proxify(self, obj, func):
        # Do not really proxify. Overloaded in subclasses.
        self.exec_setter(obj, func)

    def setter(self, obj, func, *names):
        obj, can_proxify = self.prepare_obj(obj, func, names)

        # sometimes real setting can be deferred
        if can_proxify:
            self.proxify(obj, func)
        else:
            self.exec_setter(obj, func)

        return obj


class ProxifyingExecContext(ExecContext):
    """docstring for ProxifyingExecContext"""

    def __init__(self):
        super(ProxifyingExecContext, self).__init__()

        self.todo = dict()  # {id: (cls, obj, func)}
        self.proxy_type_dict = dict(proxy.type_dict,
                                    __my_proxy_resolve__=self.resolve)
        self.proxy_type_map = dict()

    def proxify(self, obj, func):
        cls = type(obj)
        try:
            proxy_type = self.proxy_type_map[cls]
        except KeyError:
            proxy_type = self.proxy_type_map[cls] = \
                type('_proxy_for_{0.__name__}'.format(cls),
                     (cls,), self.proxy_type_dict)

        obj.__class__ = proxy_type  # danger, danger...
        self.todo[id(obj)] = (cls, obj, func)

    def restore_and_resolve(self, cls, obj, func):
        cls.__setattr__(obj, '__class__', cls)
        self.exec_setter(obj, func)

    def resolve(self, obj):
        try:
            cls, obj, func = self.todo.pop(id(obj))
        except KeyError:
            pass
        else:
            self.restore_and_resolve(cls, obj, func)

    def resolve_all(self):
        for _, (cls, obj, func) in pop_iter(self.todo, pop_meth='popitem'):
            self.restore_and_resolve(cls, obj, func)


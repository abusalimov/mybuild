"""
Object proxification, mostly derived from unittest.mock library.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-08-22"

from _compat import *


magic_methods = {}
to_magic = '__{0}__'.format


builtin_magics = (
    "len iter "
    "hash str repr "
    "divmod complex int float "
).split()

if py3k:
    builtin_magics += 'bool next '.split()
else:
    builtin_magics += 'unicode long oct hex '.split()

for name in builtin_magics:
    magic_methods[name] = eval(name)

if not py3k:
    magic_methods['nonzero'] = bool


import operator
operator_magics = (
    "lt le gt ge eq ne "
    "getitem setitem delitem contains "
    "neg pos abs invert index "
).split()

num_ops = "add sub mul div floordiv mod lshift rshift and xor or pow ".split()
if not py3k:
    num_ops += ["truediv"]

num_iops = list(map('i{0}'.format, num_ops))

for name in (operator_magics + num_ops + num_iops):
    magic_methods[name] = getattr(operator, to_magic(name))

def _num_rop(op):
    return lambda a, b: op(b, a)

for name in num_ops:
    magic_methods['r'+name] = _num_rop(getattr(operator, to_magic(name)))


import math
math_magics = (
    "trunc floor ceil "
).split()


for name in math_magics:
    magic_methods[name] = getattr(math, name)


# not including __prepare__, __instancecheck__, __subclasscheck__
# (as they are metaclass methods)
# __del__ is not supported at all as it causes problems if it exists

reinvoke_magics = (
    "init new "
    "getattr setattr "

    # non defaults
    "cmp getslice setslice coerce subclasses "
    "format get set delete reversed "
    "missing reduce reduce_ex getinitargs "
    "getnewargs getstate setstate getformat "
    "setformat repr dir "

    "enter exit "
    "sizeof "

    # metaclass methods
    "instancecheck subclasscheck "
    "prepare "
).split()


def _invoke(name):
    return lambda self, *args, **kwargs: getattr(self, name)(*args, **kwargs)

for name in reinvoke_magics:
    magic_methods[name] = _invoke(to_magic(name))


def niy_resolve(*args, **kwargs):
    raise NotImplementedError("Implementation must restore the actual type")
magic_methods['my_proxy_resolve'] = niy_resolve


def resolve_proxy(self):
    type(self).__my_proxy_resolve__(self)  # restores the original type

def magic_entry(name, func):
    magic = to_magic(name)

    def method(self, *args, **kwargs):
        resolve_proxy(self)
        return func(self, *args, **kwargs)
    method.__name__ = magic

    return magic, method


type_dict = dict(magic_entry(name, func)
                 for name, func in iteritems(magic_methods))



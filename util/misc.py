"""
Misc stuff.
"""
from __future__ import absolute_import


from _compat import *

from collections import namedtuple as _namedtuple
import json as _json
import string as _string

from util.collections import is_mapping


class Pair(_namedtuple('_Pair', 'false true')):
    __slots__ = ()

    def _mapwith(self, func):
        return Pair._make(map(func, self))

bools = Pair(False, True)


def to_dict(iterable_or_mapping, check_exclusive=False):
    if isinstance(iterable_or_mapping, dict):
        return iterable_or_mapping

    if not check_exclusive or is_mapping(iterable_or_mapping):
        return dict(iterable_or_mapping)

    items = list(iterable_or_mapping)
    ret_dict = dict(items)
    if len(ret_dict) != len(items):
        raise ValueError('Item(s) with conflicting keys detected')

    return ret_dict


def stringify(s):
    return (_json.dumps(s)
            .replace(r'\u0007', r'\a')
            .replace(r'\u000b', r'\v'))


if hasattr(0, 'bit_length'):
    def single_set_bit(x):
        if x > 0 and not (x & (x-1)):
            return x.bit_length() - 1

else:
    def single_set_bit(x):
        if x > 0 and not (x & (x-1)):
            return len(bin(x)) - 3  # 5 -> bin=0b101 -> len=5 -> ret=2


def singleton(cls):
    """Decorator for declaring and instantiating a class in-place."""
    return cls()


class NotifyingMixin(object):
    """docstring for NotifyingMixin"""
    __slots__ = '__subscribers'

    def __init__(self):
        super(NotifyingMixin, self).__init__()
        self.__subscribers = []

    def _notify(self, *args, **kwargs):
        for func in self.__subscribers:
            func(*args, **kwargs)

    def subscribe(self, func):
        self.__subscribers.append(func)


class InstanceBoundTypeMixin(object):
    """
    Base class for per-instance types, that is types defined for each instance
    of the target type.

    Do not use without mixing in a instance-private type.
    """
    __slots__ = ()

    # These may be too strict checks, but it is OK,
    # since types are mapped to the corresponding instances one-to-one.
    _type_eq   = classmethod(lambda cls, other: cls is type(other))
    _type_hash = classmethod(id)

    def __eq__(self, other):
        return self._type_eq(other)
    def __hash__(self):
        return self._type_hash()


class BaseObjectTypeMeta(type):
    """Makes classes inherit a certain base type instead of the 'object'."""

    _object_type = object

    @classmethod
    def _default_object_type(mcls, object_type):
        """Set the base type to a given one.

        Suitable for use as a decorator.
        """
        if not issubclass(object_type, mcls._object_type):
            raise TypeError("Metaclass '{mcls}' has already got "
                            "a base type '{mcls._object_type}' registered "
                            "that belongs to a different type hierarchy "
                            "than '{object_type}'".format(**locals()))

        mcls._object_type = object_type

        return object_type

    def __new__(mcls, name, bases, attrs, object_type=None, **kwargs):
        if object_type is None:
            object_type = mcls._object_type

        if not any(issubclass(base, object_type) for base in bases):
            # Neither of bases extend the default object type, so we need to
            # add it explicitly.
            #
            # The way we do it can actually hide some potential errors,
            # like when the original bases would produce an inconsistent MRO,
            # but this would only probably happen in case the object type we
            # add has itself a complex type hierarchy.
            bases = (tuple(base for base in bases
                           if not issubclass(object_type, base)) +
                     (object_type,))

        return super(BaseObjectTypeMeta, mcls).__new__(mcls,
                                                       name, bases, attrs,
                                                       **kwargs)

    def __init__(cls, name, bases, attrs, object_type=None, **kwargs):
        super(BaseObjectTypeMeta, cls).__init__(name, bases, attrs, **kwargs)

    def _meta_for_object_type(cls, **base_kwargs):
        default_kwargs = dict(metaclass=type(cls), object_type=cls)
        base_kwargs = dict(default_kwargs, **base_kwargs)

        def meta(name, bases, attrs, **kwargs):
            kwargs = dict(base_kwargs, **kwargs)
            return new_type(name, bases, attrs, **kwargs)

        return meta


class ConsumeKwargsMeta(type):
    """Suppress any metaclass keyword arguments.

    Assumed to be the last one in the metaclass MRO before the 'type' type.
    """

    def __new__(mcls, name, bases, attrs, **kwargs):
        return super(ConsumeKwargsMeta, mcls).__new__(mcls, name, bases, attrs)
    def __init__(cls, name, bases, attrs, **kwargs):
        super(ConsumeKwargsMeta, cls).__init__(name, bases, attrs)

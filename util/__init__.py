"""
Misc stuff. --Eldar
"""

from functools import partial
from operator import attrgetter
from operator import itemgetter
from operator import methodcaller

from .collections import Mapping as _Mapping
from .collections import namedtuple as _namedtuple

from .compat import *


def identity(x):
    return x


class cached_property(object):
    """Non-data descriptor."""
    __slots__ = 'func'

    def __init__(self, func):
        super(cached_property, self).__init__()
        self.func = func

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        func = self.func
        ret = func(obj)
        setattr(obj, func.__name__, ret)
        return ret


class intercepting_property(property):
    """Data descriptor."""
    __slots__ = 'name'

    def __init__(self, fget=None, fset=None, fdel=None, name=None, doc=None):
        func = fget or fset or fdel

        if name is None:
            if func is not None:
                name = func.__name__
            else:
                raise TypeError('no attribute name given')

        super(intercepting_property, self).__init__(fget, fset, fdel, doc)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            ret = obj.__dict__[self.name]
        except KeyError:
            raise AttributeError
        fget = self.fget
        if fget is not None:
            ret = fget(obj, ret)
        return ret

    def __set__(self, obj, value):
        fset = self.fset
        if fset is not None:
            value = fset(obj, value)
        obj.__dict__[self.name] = value

    def __delete__(self, obj):
        fdel = self.fdel
        if fdel is not None:
            fdel(obj)
        try:
            del obj.__dict__[self.name]
        except KeyError:
            raise AttributeError


class GetterType(object):
    """
    getter.attr  -> attrgetter('attr')
    getter[item] -> itemgetter(item)
    """

    def __getattr__(self, attr):
        return attrgetter(attr)

    def __getitem__(self, item):
        return itemgetter(item)

getter = GetterType()


class InvokerType(object):
    """
    invoker.meth(*args, **kwargs) -> methodcaller('meth', *args, **kwargs)
    """

    def __getattr__(self, meth):
        return partial(methodcaller, meth)

invoker = InvokerType()


class Pair(_namedtuple('_Pair', 'false true')):
    __slots__ = ()

    def _mapwith(self, func):
        return Pair._make(map(func, self))

bools = Pair(False, True)


def to_dict(iterable_or_mapping, check_exclusive=False):
    if isinstance(iterable_or_mapping, dict):
        return iterable_or_mapping

    if not check_exclusive or isinstance(iterable_or_mapping, _Mapping):
        return dict(iterable_or_mapping)

    items = list(iterable_or_mapping)
    ret_dict = dict(items)
    if len(ret_dict) != len(items):
        raise ValueError('Item(s) with conflicting keys detected')

    return ret_dict


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


def pop_iter(s, pop=None, pop_meth='pop'):
    get_next = pop if pop is not None else getattr(s, pop_meth)
    while s:
        yield get_next()

def send_next_iter(it, first=None):
    get_next = iter(it).next
    received = first
    while True:
        received = (yield received if received is not None else get_next())
        if received is not None:
            yield  # from send


def until_fixed(func):
    prev = func()
    yield prev

    next = func()

    while prev != next:
        yield next

        prev = next
        next = func()

def unique(iterable, key=id):
    """
    List unique elements, preserving order. Remember all elements ever seen.
    """
    seen = set()
    seen_add = seen.add
    for element in iterable:
        k = key(element)
        if k not in seen:
            seen_add(k)
            yield element

def filter_bypass(function, exception, iterable):
    if function is None:
        return list(iterable)

    def predicate(e):
        try:
            function(e)
        except exception:
            return False
        else:
            return True
    return filter(predicate, iterable)

def map_bypass(function, exception, *iterables):
    return list(imap_bypass(function, exception, *iterables))

def imap_bypass(function, exception, *iterables):
    if function is None:
        function = lambda *args: tuple(args)

    iterables = map(iter, iterables)

    while True:
        args = [it.next() for it in iterables]
        try:
            e = function(*args)
        except exception:
            pass
        else:
            yield e


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
        return self._type_eq(type(other))
    def __hash__(self):
        return self._type_hash()


"""
Misc stuff.
"""
from __future__ import absolute_import


from _compat import *

import functools as _functools
from functools import partial

from collections import namedtuple as _namedtuple
from collections import deque as _deque

from util.itertools import pop_iter
from util.collections import is_mapping


def constructor_decorator(cls, **kwargs):
    """
    Lets using a decorated class as a function decorator, which converts the
    function into a constructor.

    Note: this function returns a fake class which is replaced by the original
    one upon subclassing, thus it doesn't appear in MRO of subclasses. This
    means that the class returned must not be used in super().

    Keyword arguments are used to alter attributes of the returned class.
    """

    # For 'cls' itself we define a fake metaclass, which overrides a default
    # __call__ method to accept function objects. On the other hand, it is only
    # used to instantiate the returned class; when subclassing it the metaclass
    # replaces itself with the original one and replaces the returned class
    # with 'cls' with the original __call__ method.
    #
    # This magic is similar to the one used in util.compat.with_metaclass
    # function.
    mcls = type(cls)

    class metaclass(mcls):
        __init__ = type.__init__
        def __new__(xmcls, name, this_bases, attrs):
            if this_bases is None:
                return type.__new__(xmcls, name, (cls,), attrs)
            bases = tuple(base if base is not ret_cls else cls
                          for base in this_bases)
            return mcls(name, bases, attrs)

        def __call__(xcls, func):
            # For unknown reasons __doc__ attribute of type objects is
            # read-only, and update_wrapper is unable to set it. The same is
            # about __dict__  attribute which becomes a dictproxy upon class
            # definition, not a dict.
            #
            # So instead we create a new type manually.
            @_functools.wraps(func)
            def __init__(self, *args, **kwargs):
                super(ret_type, self).__init__(*args, **kwargs)
                return func(self, *args, **kwargs)
            type_dict = dict(func.__dict__,
                             __init__   = __init__,
                             __module__ = __init__.__module__,
                             __doc__    = __init__.__doc__)
            ret_type = mcls(func.__name__, (cls,), type_dict)
            return ret_type

    ret_cls = metaclass(cls.__name__, None, dict(cls.__dict__, **kwargs))
    return ret_cls


def no_reent(func, reent_manager=None):
    """Decorator which defers recursive calls to 'func' to the outermost
    invocation."""
    if reent_manager is None:
        reent_manager = ReentManager()

    @_functools.wraps(func)
    def decorated(*args, **kwargs):
        return reent_manager.post(partial(func, *args, **kwargs))
    decorated.no_reent = partial(no_reent, reent_manager=reent_manager)

    return decorated


class ReentManager(object):
    """Job mgmt."""
    __slots__ = '_job_queue', '_outermost'

    def __init__(self):
        super(ReentManager, self).__init__()
        self._job_queue = _deque()
        self._outermost = True

    def post(self, func):
        was_outermost = self._outermost
        self._outermost = False

        self._job_queue.append(func)

        if was_outermost:
            try:
                for job_func in pop_iter(self._job_queue, pop_meth='popleft'):
                    job_func()
            finally:
                self._outermost = True


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
        return self._type_eq(type(other))
    def __hash__(self):
        return self._type_hash()


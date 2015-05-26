"""
Extends the standard itertools module.
"""
from __future__ import absolute_import


from _compat import *

from itertools import *
from functools import partial


def raises(exception, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exception:
        return True
    else:
        return False


def hasnext(it):
    return not raises(StopIteration, next, it)


def pop_iter(collection, pop=None, pop_meth='pop'):
    if pop is None:
        pop = getattr(collection, pop_meth)
    while collection:
        yield pop()

def attr_chain_iter(obj, attr, with_self=False):
    if obj is not None and not with_self:
        obj = getattr(obj, attr)

    while obj is not None:
        yield obj
        obj = getattr(obj, attr)


def send_next_iter(it, first=None):
    it = iter(it)
    received = first
    while True:
        received = (yield received if received is not None else next(it))
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
    return unique_values((key(element), element) for element in iterable)

def unique_values(pairs):
    seen = set()
    seen_add = seen.add
    for k, v in pairs:
        if k not in seen:
            seen_add(k)
            yield v

def filter_bypass(func, exception, iterable):
    if func is None:
        return iterable

    return filternot(partial(raises, exception, func), iterable)

def map_bypass(func, exception, *iterables):
    if func is None:
        func = lambda *args: args

    iterables = tuple(map(iter, iterables))

    while True:
        args = tuple(map(next, iterables))
        try:
            e = func(*args)
        except exception:
            pass
        else:
            yield e


"""
Extends the standard itertools module.
"""
from __future__ import absolute_import

from itertools import *

from .compat import *


def raises(exception, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exception:
        return True
    else:
        return False


def hasnext(it):
    return not raises(StopIteration, next, it)

def pop_iter(s, pop=None, pop_meth='pop'):
    get_next = pop if pop is not None else getattr(s, pop_meth)
    while s:
        yield get_next()

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
    seen = set()
    seen_add = seen.add
    for element in iterable:
        k = key(element)
        if k not in seen:
            seen_add(k)
            yield element

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


"""
2to3 compat stuff.
"""


import abc as _abc
import operator as _operator
import sys as _sys
_py3k = (_sys.version_info[0] == 3)


# builtins
if _py3k:
    range  = range
    filter = filter
    map    = map
    zip    = zip
    next   = next

else:
    range = xrange
    from itertools import ifilter as filter
    from itertools import imap    as map
    from itertools import izip    as zip
    next = _operator.methodcaller('next')


if _py3k:
    from itertools import filterfalse as filternot
else:
    from itertools import ifilterfalse as filternot


# dict iterators
if _py3k:
    itervalues = lambda d: iter(d.values())
    iteritems  = lambda d: iter(d.items())
else:
    itervalues = _operator.methodcaller('itervalues')
    iteritems  = _operator.methodcaller('iteritems')

iterkeys = iter


def extend(*bases, **kwargs):
    """Allows one to use some of Py3k metaclass features from PEP 3115.

    Basically this function is used instead of a list of bases in a class
    definition. It allows to specify a metaclass using **kwargs syntax as well
    as passing arbitrary keyword arguments to the metaclass.

    Note: extend(...) must be the sole base class in a class definition.
    Also note that due to some interpreter bugs you should avoid using this
    trick with dynamic type creation (type(name, bases, attrs))."""

    base = bases[0] if bases else object
    meta = kwargs.pop('metaclass', type(base))
    if meta is type and len(bases)<=1 and not kwargs:
        return base

    if isinstance(meta, type):
        # when meta is a type, we first determine the most-derived metaclass
        # instead of invoking the initial candidate directly
        meta_type = meta = _calculate_meta(meta, bases)
    else:
        meta_type = type

    class temp_metaclass(meta_type):
        # Derived from Jinja2.
        #
        # This requires a bit of explanation: the basic idea is to make a
        # dummy metaclass for one level of class instantiation that replaces
        # itself with the actual metaclass.  Because of internal type checks
        # we also need to make sure that we downgrade the custom metaclass
        # for one level to something closer to type (that's why __init__ comes
        # back from type etc.).
        #
        # This has the advantage over six.with_metaclass in that it does not
        # introduce dummy classes into the final MRO.
        __init__ = type.__init__
        def __new__(mcls, name, this_bases, attrs):
            if this_bases is None:  # creating temp_class
                return type.__new__(mcls, name, (), attrs)
            try:
                _, = this_bases  # it must be a tuple of a single element
            except ValueError:
                # class C(extend(...), something_else): ...
                # or bases is not a singlular tuple in a metaclass call
                raise TypeError("'extend(...)' must be the sole base class "
                                "in a class definition")
            return meta(name, bases, attrs, **kwargs)

    return temp_metaclass('temp_class', None, {})


# derived from Py3k Lib/types.py
def _calculate_meta(meta, bases):
    """Calculate the most derived metaclass."""
    winner = meta
    for base in bases:
        base_meta = type(base)
        if issubclass(winner, base_meta):
            continue
        if issubclass(base_meta, winner):
            winner = base_meta
            continue
        # else:
        raise TypeError("metaclass conflict: "
                        "the metaclass of a derived class "
                        "must be a (non-strict) subclass "
                        "of the metaclasses of all its bases")
    return winner


ABCBase = extend(metaclass=_abc.ABCMeta)


def new_type(name, bases, attrs, **kwargs):
    """Replacement for 3-arg form of type(...) builtin function.

    Also accepts optional metaclass keyword arguments and contains
    workarounds for known interpreter bugs."""

    temp_class = extend(*bases, **kwargs)
    return type(temp_class)(name, (temp_class,), attrs)


import functools as _functools
def _foo(): pass
def _bar(): pass
_functools.update_wrapper(_foo, _bar)
if not hasattr(_foo, '__wrapped__'):
    def _patch_it(wrapped_func):
        def wrapper_func(wrapper, wrapped, *args, **kwargs):
            ret = wrapped_func(wrapper, wrapped, *args, **kwargs)
            wrapper.__wrapped__ = wrapped
            return ret
        return wrapper_func(wrapper_func, wrapped_func)
    _functools.update_wrapper = _patch_it(_functools.update_wrapper)
    del _patch_it
del _foo
del _bar
del _functools

import inspect as _inspect
if not hasattr(_inspect, 'unwrap'):
    def unwrap(func, stop=None):
        """Get the object wrapped by *func*.

       Follows the chain of :attr:`__wrapped__` attributes returning the last
       object in the chain.

       :exc:`ValueError` is raised if a cycle is encountered.

        """
        if stop is None:
            def _is_wrapper(f):
                return hasattr(f, '__wrapped__')
        else:
            def _is_wrapper(f):
                return hasattr(f, '__wrapped__') and not stop(f)
        f = func  # remember the original func for error reporting
        memo = set([id(f)]) # Memoise by id to tolerate non-hashable objects
        while _is_wrapper(func):
            func = func.__wrapped__
            id_func = id(func)
            if id_func in memo:
                raise ValueError('wrapper loop when unwrapping {!r}'.format(f))
            memo.add(id_func)
        return func
    _inspect.unwrap = unwrap
del _inspect


del _abc
del _operator
del _sys
del _py3k

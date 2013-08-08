"""
2to3 compat stuff.
"""
from __future__ import absolute_import

import abc as _abc
import operator as _operator
import sys as _sys
_py3k = (_sys.version_info[0] == 3)


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

from itertools import ifilterfalse as filternot


if _py3k:
    itervalues = lambda d: iter(d.values())
    iteritems  = lambda d: iter(d.items())

else:
    itervalues = _operator.methodcaller('itervalues')
    iteritems  = _operator.methodcaller('iteritems')

iterkeys = iter


def with_meta(*meta_arg, **kwargs):
    if meta_arg:
        meta, = meta_arg
    else:
        meta = None
    # Derived from Jinja2.
    #
    # This requires a bit of explanation: the basic idea is to make a
    # dummy metaclass for one level of class instantiation that replaces
    # itself with the actual metaclass.  Because of internal type checks
    # we also need to make sure that we downgrade the custom metaclass
    # for one level to something closer to type (that's  __init__ comes
    # back from type etc.).
    #
    # This has the advantage over six.with_metaclass in that it does not
    # introduce dummy classes into the final MRO.
    class metaclass(meta or type):
        __init__ = type.__init__
        def __new__(mcls, name, this_bases, attrs):
            if this_bases is None:
                return type.__new__(mcls, name, (), attrs)
            bases = tuple(base for base in this_bases
                          if base is not temp_class)
            mcls = meta or compute_default_metaclass(bases)
            return mcls(name, bases, attrs, **kwargs)
    temp_class = metaclass('temp_class', None, {})

    return temp_class

# derived from Py3k Lib/types.py
def compute_default_metaclass(bases):
    """Calculate the most derived metaclass."""
    winner = type
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

ABCBase = with_meta(_abc.ABCMeta)


del _abc
del _operator
del _sys
del _py3k

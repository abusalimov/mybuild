"""
Declarative deep copy and type checking for compound data structures.
"""
from __future__ import absolute_import

__author__ = "Eldar Abusalimov"
__date__ = "2015-06-12"

__all__ = [
    "conv",
]


from _compat import *

import functools
import inspect
from itertools import starmap

from util.misc import check_type
from util.misc import raise_type_error


def conv(value, to=None):
    """Deep copy mutable collections and check types based on a given spec.

    Example:
    >>> pairs = [('a', 42), ('b', 17)]
    >>> (conv(pairs, [('letter', int)]) ==
    ...  conv(pairs, [(str, int)]) ==
    ...  conv(pairs, [tuple]) ==
    ...  conv(pairs, []) ==
    ...  conv(pairs, list) ==
    ...  pairs)
    True
    >>> conv(pairs, [('letter', int)]) is pairs
    False
    >>> conv(pairs) is pairs
    True
    >>> conv(pairs, {'letter': int}) == conv(pairs, dict) == dict(a=42, b=17)
    True
    """
    if to is None:
        return value

    if to is callable:
        if not callable(value):
            raise_type_error(value, 'callable')
        return value

    if (isinstance(to, type) and
        issubclass(to, string_types + integer_types +
                   (list, tuple, dict, set, frozenset))):
        to_type = to
        to = None
    else:
        to_type = type(to)
    if isinstance(to, (list, tuple, dict, set, frozenset)) and not to:
        to = None

    if issubclass(to_type, string_types):
        return check_type(value, string_types, 'string')    # any string is OK
    if issubclass(to_type, integer_types):
        return check_type(value, integer_types, 'integer')  # ditto

    if to is None:  # a collection of any elements
        if (not isinstance(value, to_type) or              # type mismatch
            not issubclass(to_type, (tuple, frozenset))):  # or not immutable
            value = to_type(value)
        return value

    if issubclass(to_type, tuple):
        if not isinstance(value, to_type):
            value = to_type(value)
        if len(value) != len(to):
            raise ValueError("Too {} values to unpack as {!r}: '{}'"
                             .format('few' if len(value) < len(to) else 'many',
                                     to, value))
        return to_type(starmap(conv, zip(value, to)))

    if issubclass(to_type, (dict, list, set, frozenset)):
        if len(to) != 1:
            raise ValueError('Need exactly 1 value in conv spec: {!r}'
                             .format(to))

        if issubclass(to_type, dict):
            if isinstance(value, to_type):
               value = iteritems(value)
            elif hasattr(value, 'keys'):
               value = iteritems(dict(value))
            (k_to, v_to), = to.items()
            return to_type((conv(k, k_to), conv(v, v_to)) for k, v in value)

        else:
            el_to, = to
            return to_type(conv(el, el_to) for el in value)

    return check_type(value, to_type)


def conv_args(*func_arg, **spec_kwargs):
    if len(func_arg) > 1 or func_arg and spec_kwargs:
        raise TypeError('conv_args() takes either a single positional '
                        'argument or solely keyword arguments')

    def decorator(func):
        orig_func = inspect.unwrap(func)
        pos_names, va_nm, kw_nm, defaults = inspect.getargspec(orig_func)
        if va_nm in spec_kwargs or kw_nm in spec_kwargs:
            raise NotImplementedError('Star args not supported')
        num_pos = len(pos_names)
        idx_default = num_pos - len(defaults or ())
        name_defaults = list(zip(pos_names[idx_default:], defaults or ()))
        get_spec = spec_kwargs.get

        @functools.wraps(func)
        def decorated(*args, **kwargs):
            print(args, kwargs)
            num_args = len(args)

            args = tuple(conv(value, get_spec(name))
                         for name, value in zip(pos_names, args))

            if num_args < num_pos:
                args += args[num_pos:]
                defaults_left = name_defaults[min(0, num_args - idx_default):]
                if defaults_left:
                    kwargs = dict(defaults_left, **kwargs)

            kwargs = dict((name, conv(value, get_spec(name)))
                          for name, value in iteritems(kwargs))

            print(args, kwargs)
            return func(*args, **kwargs)

        return decorated

    if func_arg:
        func = func_arg[0]
        spec_kwargs = dict(func.__annotations__)
        spec_kwargs.pop('return', None)
        return decorator(func)

    return decorator


if __name__ == '__main__':
    import doctest
    doctest.testmod()


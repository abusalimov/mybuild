"""
Mybuild.
TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__copyright__ = "Copyright 2012, The Embox Project"
__license__ = "New BSD"
__version__ = "0.5"

__all__ = ['core', 'module', 'option']

import functools

import core


class module(core.Module):
    """
    Example of a simple module without any options:

    >>> @module
    ... def modname(self):
    ...     pass

    """
    def __init__(self, fxn):
        super(module, self).__init__(fxn)
        functools.update_wrapper(self, fxn)


class option(core.Option):
    """
    More examples:

    >>> @module
    ... def m(self,
    ...       foo = option(0, 'one', 'two'),    # one of these, or any other
    ...       bar = option.enum(38400, 115200), # enumeration of two values
    ...       baz = option.bool(default=True),  # boolean flag
    ...         ):
    ...     pass

    """


if __name__ == '__main__':
    import doctest
    doctest.testmod()


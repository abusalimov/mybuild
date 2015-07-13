"""
Property descriptors.
"""


from _compat import *

from functools import partial as _partial


class _func_deco(object):

    def __init__(self, func):
        super(_func_deco, self).__init__()
        self.func = func


class _func_deco_with_attr(_func_deco):

    def __init__(self, func, attr=None):
        super(_func_deco_with_attr, self).__init__(func)
        if attr is None:
            attr = func.__name__
        self.attr = attr


class class_instance_method(_func_deco):
    """Non-data descriptor.

    Methods decorated by this class must accept two special arguments (go
    first): cls and self: cls is the same as for classmethod, self is None
    in case of invoking on the class and the instance otherwise.

    Usage example:

    >>> class C(object):
    ...     @class_instance_method
    ...     def meth(cls, self, arg):
    ...         print("Invoking {cls.__name__}.meth on {self} with {arg}"
    ...               .format(**locals()))
    ...         return arg
    ...     def __repr__(self):
    ...         return "<{cls.__name__} object>".format(cls=type(self))
    ...
    >>> C.meth(17)
    Invoking C.meth on None with 17
    17
    >>> x = C()
    >>> x.meth(42)
    Invoking C.meth on <C object> with 42
    42
    """

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return _partial(self.func, objtype, obj)


class default_property(_func_deco):
    """Non-data descriptor.

    Delegates to func everytime a property is accessed unless someone
    explicitly overrides it by setting a new value.

    Usage example:

    >>> class C(object):
    ...     @default_property
    ...     def default(self):
    ...         print("Accessing {cls.__name__}.default"
    ...               .format(cls=type(self)))
    ...         return 17
    ...
    >>> C.default  # doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
        ...
    AttributeError: 'default_property' descriptor 'default' of 'C' objects \
    is not accessible as a class attribute
    >>> x = C()
    >>> x.default
    Accessing C.default
    17
    >>> x.default
    Accessing C.default
    17
    >>> x.default = 42
    >>> x.default
    42
    """

    def __get__(self, obj, objtype=None):
        if obj is None:
            raise AttributeError("'{self.__class__.__name__}' descriptor "
                                 "'{self.func.__name__}' "
                                 "of '{objtype.__name__}' objects is not "
                                 "accessible as a class attribute"
                                 .format(**locals()))
        return self.func(obj)


class cached_property(default_property, _func_deco_with_attr):
    """Non-data descriptor.

    Delegates to func only the first time a property is accessed.

    Usage example:

    >>> class C(object):
    ...     @cached_property
    ...     def cached(self):
    ...         print("Accessing {cls.__name__}.cached".format(cls=type(self)))
    ...         return 17
    ...
    >>> x = C()
    >>> x.cached
    Accessing C.cached
    17
    >>> x.cached
    17
    >>> x.cached = 42
    >>> x.cached
    42
    """

    def __get__(self, obj, objtype=None):
        ret = super(cached_property, self).__get__(obj, objtype)
        setattr(obj, self.attr, ret)
        return ret


class default_class_property(_func_deco):
    """Non-data descriptor.

    Calls func on an instance type everytime a property is accessed.

    Usage example:

    >>> class C(object):
    ...     @default_class_property
    ...     def prop(cls):
    ...         print("Accessing {cls.__name__}.prop"
    ...               .format(**locals()))
    ...         return 17
    ...
    >>> C.prop
    Accessing C.prop
    17
    >>> x = C()
    >>> x.prop
    Accessing C.prop
    17
    >>> x.prop = 42
    >>> x.prop
    42
    """

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        return self.func(objtype)


class cached_class_property(default_class_property, _func_deco_with_attr):
    """Non-data descriptor.

    Delegates to func only the first time a property is accessed.

    Usage example:

    >>> class C(object):
    ...     @cached_class_property
    ...     def cached(cls):
    ...         print("Accessing {cls.__name__}.cached"
    ...               .format(**locals()))
    ...         return 17
    ...
    >>> x = C()
    >>> x.cached
    Accessing C.cached
    17
    >>> C.cached
    17
    >>> y = C()
    >>> y.cached
    17
    >>> y.cached = 42
    >>> y.cached
    42
    """

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)
        ret = super(cached_class_property, self).__get__(obj, objtype)
        setattr(objtype, self.attr, ret)
        return ret


if __name__ == '__main__':
    import doctest
    doctest.testmod()

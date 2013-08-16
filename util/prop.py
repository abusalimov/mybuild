"""
Property descriptors.
"""


from _compat import *


class default_property(object):
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
    __slots__ = 'func'

    def __init__(self, func):
        super(default_property, self).__init__()
        self.func = func

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return self.func(obj)


class cached_property(default_property):
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
    __slots__ = ()

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        ret = super(cached_property, self).__get__(obj, objtype)
        setattr(obj, self.func.__name__, ret)
        return ret


class intercepting_property(property):
    """Data descriptor.
    Usage example:

    >>> class C(object):
    ...     @intercepting_property
    ...     def icp(self, value):
    ...         print("Get {cls.__name__}.icp: {value}"
    ...               .format(cls=type(self), **locals()))
    ...         return -value
    ...     @icp.setter
    ...     def icp(self, value):
    ...         print("Set {cls.__name__}.icp: {value}"
    ...               .format(cls=type(self), **locals()))
    ...         return -value
    ...     @icp.deleter
    ...     def icp(self):
    ...         print("Del {cls.__name__}.icp".format(cls=type(self)))
    ...
    >>> x = C()
    >>> x.icp
    Traceback (most recent call last):
        ...
    AttributeError: 'C' object has no attribute 'icp'
    >>> x.icp = 7
    Set C.icp: 7
    >>> x.__dict__['icp']
    -7
    >>> x.icp
    Get C.icp: -7
    7
    >>> del x.icp
    Del C.icp
    >>> 'icp' in x.__dict__
    False
    """

    def __init__(self, fget=None, fset=None, fdel=None, name=None, doc=None):
        super(intercepting_property, self).__init__(fget, fset, fdel, doc)

        if name is None:
            func = fget or fset or fdel
            if func is None:
                raise TypeError('no attribute name given')
            name = func.__name__

        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            ret = obj.__dict__[self.name]
        except KeyError:
            raise AttributeError("'{objtype.__name__}' object has no "
                                 "attribute '{self.name}'".format(**locals()))
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
            objtype = type(obj)
            raise AttributeError("'{objtype.__name__}' object has no "
                                 "attribute '{self.name}'".format(**locals()))


if __name__ == '__main__':
    import doctest
    doctest.testmod()


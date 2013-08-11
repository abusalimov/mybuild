"""
Property descriptors.
"""


from _compat import *


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



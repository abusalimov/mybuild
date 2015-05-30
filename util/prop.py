"""
Property descriptors.
"""


from _compat import *

import weakref as _weakref
from collections import defaultdict as _defaultdict
from functools import partial as _partial


class _func_deco(object):

    def __init__(self, fget):
        super(_func_deco, self).__init__()
        self.fget = fget


class _func_deco_with_attr(_func_deco):

    def __init__(self, fget, attr=None):
        super(_func_deco_with_attr, self).__init__(fget)
        if attr is None:
            attr = fget.__name__
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
        return _partial(self.fget, objtype, obj)


class default_property(_func_deco):
    """Non-data descriptor.

    Delegates to a getter every time a property is accessed unless someone
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
                                 "'{self.fget.__name__}' "
                                 "of '{objtype.__name__}' objects is not "
                                 "accessible as a class attribute"
                                 .format(**locals()))
        return self.fget(obj)


class cached_property(default_property, _func_deco_with_attr):
    """Non-data descriptor.

    Delegates to a getter only the first time a property is accessed.

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

    Calls a getter on an instance type every time a property is accessed.

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
        return self.fget(objtype)


class cached_class_property(default_class_property, _func_deco_with_attr):
    """Non-data descriptor.

    Delegates to a getter only the first time a property is accessed and
    memorizes the result replacing the descriptor in the class __dict__.

    Usage example:

    >>> class C(object):
    ...     @cached_class_property
    ...     def cached(cls):
    ...         print("Accessing {cls.__name__}.cached"
    ...               .format(**locals()))
    ...         return 17
    ...
    >>> class D(C):
    ...     pass
    ...
    >>> x = C()
    >>> x.cached
    Accessing C.cached
    17
    >>> C.cached
    17
    >>> y = D()
    >>> y.cached
    Accessing D.cached
    17
    >>> y.cached = 42
    >>> y.cached
    42
    """

    @property
    def _cls_cache(self):
        return self.__cls_caches[self.attr]

    def __init__(self, fget, attr=None):
        super(cached_class_property, self).__init__(fget, attr)
        self.__cls_caches = _defaultdict(_weakref.WeakKeyDictionary)

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)

        try:
            ret = self._cls_cache[objtype]
        except KeyError:
            ret = self._cls_cache[objtype] = \
                    super(cached_class_property, self).__get__(obj, objtype)

        return ret


class lazy_const_class_property(default_class_property, _func_deco_with_attr):
    """Non-data descriptor.

    Delegates to a getter only the first time a property is accessed. However,
    unlike cached_class_property, it caches the result in a __dict__ of the
    class defining the property (even if called on some subclass), replacing
    the descriptor completely.

    Usage example:

    >>> class C(object):
    ...     @lazy_const_class_property
    ...     def lazy_const(cls):
    ...         print("Accessing {cls.__name__}.lazy_const"
    ...               .format(**locals()))
    ...         return 17
    ...
    >>> class D(C):
    ...     pass
    ...
    >>> x = D()
    >>> x.lazy_const
    Accessing C.lazy_const
    17
    >>> D.lazy_const == C.lazy_const == C.__dict__['lazy_const'] == 17
    True
    """

    def __get__(self, obj, objtype=None):
        if objtype is None:
            objtype = type(obj)

        # Instead of invoking a getter on the given class, find a base that
        # actually holds the descriptor object and invoke on that class.
        for base in objtype.__mro__:
            try:
                descr = base.__dict__[self.attr]
            except KeyError:
                continue
            if descr is self:
                break
        else:
            # This could only happen when invoking the descriptor manually,
            # or maybe on some really exotic setups.
            raise AttributeError("'{self.__class__.__name__}' descriptor "
                                 "'{self.attr}' "
                                 "of '{objtype.__name__}' objects must be "
                                 "attached to the class or to some its base"
                                 .format(**locals()))

        ret = super(lazy_const_class_property, self).__get__(obj, base)
        setattr(base, self.attr, ret)
        return ret


if __name__ == '__main__':
    import doctest
    doctest.testmod()


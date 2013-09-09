"""
Property descriptors.
"""


from _compat import *

from functools import partial as _partial
import operator as _operator


class _func_deco(object):

    def __init__(self, func):
        super(_func_deco, self).__init__()
        self.func = func


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
            return self
        return self.func(obj)


class class_default_property(_func_deco):
    """Non-data descriptor.

    Calls func on an instance type everytime a property is accessed.

    Usage example:

    >>> class C(object):
    ...     @class_default_property
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

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        ret = super(cached_property, self).__get__(obj, objtype)
        setattr(obj, self.func.__name__, ret)
        return ret


class cumulative_sequence_property(object):

    def __init__(self, factory, attr_name, add_meth_name=None):
        super(cumulative_property, self).__init__()
        self.factory       = factory
        self.attr_name     = attr_name
        self.add_meth_name = add_meth_name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            return getattr(obj, self.attr_name)
        except AttributeError:
            default = self.factory()
            setattr(obj, self.attr_name, default)
            return default

    def __set__(self, obj, items):
        try:
            old_items = getattr(obj, self.attr_name)
        except AttributeError:
            items = new_items = self.factory(items)
        else:
            new_items = self.factory(item for item in items
                                     if item not in old_items)
            items = old_items+new_items

        if self.add_meth_name is not None:
            func = getattr(obj, self.add_meth_name)

            for item in new_items:
                func(item)

        setattr(obj, self.attr_name, items)


class cumulative_property(object):

    def __init__(self, attr, factory):
        super(cumulative_property, self).__init__()
        self.attr    = attr
        self.factory = factory

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            default = self.factory()
            setattr(obj, self.attr, default)
            return default

    def split_old_new(self, obj, items):
        old_items = getattr(obj, self.attr, None)

        if old_items is not None:
            new_items = self.filter_new(items, old_items)
        else:
            new_items = items

        return old_items, self.factory(new_items)

    def filter_new(self, items, old_items):
        return items


class cumulative_mapping_property(cumulative_property):

    def __init__(self, attr, factory=dict):
        super(cumulative_mapping_property, self).__init__(attr, factory)

    def __set__(self, obj, items):
        old_items, items = self.split_old_new(obj, items)

        if old_items is not None:
            old_items.update(items)
            items = old_items

        setattr(obj, self.attr, items)

    def filter_new(self, items, old_items):
        if not isinstance(items, dict):
            items = dict(items)
        return (item for item in iteritems(items)
                if item[0] not in old_items)


class cumulative_sequence_property(cumulative_property):

    def __init__(self, attr, factory=list):
        super(cumulative_sequence_property, self).__init__(attr, factory)

    def __set__(self, obj, items):
        old_items, items = self.split_old_new(obj, items)

        if old_items is not None:
            items = _operator.__iadd__(old_items, items)

        setattr(obj, self.attr, items)

    def filter_new(self, items, old_items):
        return (item for item in items
                if item not in old_items)


class cumulative_tuple_property(cumulative_sequence_property):

    def __init__(self, attr, add_meth=None):
        super(cumulative_tuple_property, self).__init__(attr, factory=tuple)
        self.add_meth = add_meth

    def __set__(self, obj, items):
        old_items, items = self.split_old_new(obj, items)

        if self.add_meth is not None:
            func = getattr(obj, self.add_meth)

            for item in items:
                func(item)

        if old_items is not None:
            items = _operator.__iadd__(old_items, items)

        setattr(obj, self.attr, items)


class intercepting_property(property):
    """Data descriptor.

    Allows one to set hooks on get/set/del operations and to modify an actual
    value which is stored in a backing __dict__.

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


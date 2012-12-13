"""
Misc stuff. --Eldar
"""

def singleton(cls):
    """Decorator for declaring and instantiating a class in-place."""
    return cls()

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

def filter_bypass(function, exception, iterable):
    if function is None:
        return list(iterable)

    def predicate(e):
        try:
            function(e)
        except exception:
            return False
        else:
            return True
    return filter(predicate, iterable)

def map_bypass(function, exception, *iterables):
    return list(imap_bypass(function, exception, *iterables))

def imap_bypass(function, exception, *iterables):
    if function is None:
        function = lambda *args: tuple(args)

    iterables = map(iter, iterables)

    while True:
        args = [it.next() for it in iterables]
        try:
            e = function(*args)
        except exception:
            pass
        else:
            yield e


class NotifyingMixin(object):
    """docstring for NotifyingMixin"""
    __slots__ = '__subscribers'

    def __init__(self):
        super(NotifyingMixin, self).__init__()
        self.__subscribers = []

    def _notify(self, *args, **kwargs):
        for fxn in self.__subscribers:
            fxn(*args, **kwargs)

    def subscribe(self, fxn):
        self.__subscribers.append(fxn)


class InstanceBoundTypeMixin(object):
    """
    Base class for per-instance types, that is types defined for each instance
    of the target type.

    Do not use without mixing in a instance-private type.
    """
    __slots__ = ()

    # These may be too strict checks, but it is OK,
    # since types are mapped to the corresponding instances one-to-one.
    _type_eq   = classmethod(lambda cls, other: cls is type(other))
    _type_hash = classmethod(id)

    def __eq__(self, other):
        return self._type_eq(type(other))
    def __hash__(self):
        return self._type_hash()


class DynamicAttrsMixin(object):
    """
    Provides a facility for other types to register themselves to be notified
    each time when a new instance of this type gets created.
    """

    class __metaclass__(type):
        # TODO mixing in a metaclass looks like a not goog idea... -- Eldar

        def __init__(cls, *args, **kwargs):
            type.__init__(cls, *args, **kwargs)
            cls._registered_attrs = {} # attr-to-method

        def register_attr(cls, attr, factory_method='_new_type'):
            """Deco maker for per-module classes."""

            if not isinstance(attr, basestring):
                raise TypeError("Attribure name must be a string, "
                                "got %s object instead: %r" %
                                (type(attr), attr))

            if not attr.startswith('_'):
                raise ValueError("Attribute name must start with underscore")

            def deco(target):
                if not isinstance(target, type):
                    raise TypeError("'@%s.register_attr(...)' must be applied "
                                    "to a class, got %s object instead: %r" %
                                    (cls.__name__, type(target), target))

                if not hasattr(target, factory_method):
                    raise TypeError("'@%s.register_attr(...)'-decorated class "
                                    "must define a '%s' classmethod" %
                                    (cls.__name__, factory_method))

                if hasattr(cls, attr) or attr in cls._registered_attrs:
                    raise ValueError("%s class already has attribure '%s'" %
                                     (cls.__name__, attr))

                cls._registered_attrs[attr] = getattr(target, factory_method)

                return target

            return deco

    def _init_attrs(self, *args, **kwargs):
        for cls in type(self).__mro__:
            if isinstance(cls, self.__metaclass__):
                for attr, factory in cls._registered_attrs.iteritems():
                    setattr(self, attr, factory(*args, **kwargs))

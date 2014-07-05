"""
Dynamic inheritance for class members.
"""

from _compat import *
from util.itertools import pop_iter
from util.itertools import unique


class InheritMetaBase(type):

    def _kick_mro_update(cls):
        cls.__bases__ = cls.__bases__

    def mro(cls):
        meta = type(cls)
        for base in cls.__bases__:
            base_meta = type(base)
            if not issubclass(meta, base_meta):
                # Impose more strict requirements on changing __bases__,
                # see: http://bugs.python.org/issue21919
                raise TypeError("metaclass conflict: "
                                "the metaclass of a derived class "
                                "must be a (non-strict) subclass "
                                "of the metaclasses of all its bases")

        return super(InheritMetaBase, cls).mro()


class InheritOwnerMeta(InheritMetaBase):

    def __new__(mcls, name, bases, attrs):
        cls = super(InheritOwnerMeta, mcls).__new__(mcls, name, bases, attrs)

        for attr, value in iteritems(cls.__dict__):
            if isinstance(value, InheritValueMeta):
                if value._inherit_owner is not None:
                    raise ValueError

                cls.__inherit_attr(attr, value)

        return cls

    def __inherit_attr(cls, attr, value):
        value._inherit_owner = cls
        value.__bases__ = cls.__bases_for_attr(attr)

    def __bases_for_attr(cls, attr):
        base_ids = set()
        todo = list(cls.__bases__)
        for base in unique(pop_iter(todo)):
            if attr in base.__dict__:
                base_ids.add(id(base))
            else:
                todo += base.__bases__

        return [base for base in cls.__mro__ if id(base) in base_ids]


class InheritValueMeta(InheritMetaBase):

    def __init__(cls, name, bases, attrs):
        super(InheritValueMeta, cls).__init__(name, bases, attrs)
        cls._inherit_owner = None


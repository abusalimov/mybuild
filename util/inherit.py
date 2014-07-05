"""
Dynamic inheritance for class members.
"""

from _compat import *


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
    pass

class InheritValueMeta(InheritMetaBase):
    pass


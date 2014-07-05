"""
Dynamic inheritance for class members.
"""

from _compat import *
from util.itertools import pop_iter
from util.itertools import unique


class InheritMeta(type):

    def _kick_mro_update(cls):
        cls.__bases__ = cls.__bases__

    def mro(cls):
        cls.__check_base_metas(map(type, cls.__bases__))

        for attr, value in iteritems(cls.__dict__):
            if is_inherit_value(value):
                cls.__inherit_attr(attr, value)

        return super(InheritMeta, cls).mro()

    @classmethod
    def __check_base_metas(mcls, base_metas):
        for base_meta in base_metas:
            if not issubclass(mcls, base_meta):
                # Impose more strict requirements in case of changing
                # cls.__bases__, see: http://bugs.python.org/issue21919
                raise TypeError("metaclass conflict: "
                                "the metaclass of a derived class "
                                "must be a (non-strict) subclass "
                                "of the metaclasses of all its bases")

    def __check_old_owner(cls, value):
        try:
            owner_cls, owner_attr = value.__owner
        except AttributeError:
            return

        if owner_cls is not cls:
            raise ValueError("Can't inherit an owned value '{value}': "
                             "owned by '{owner_cls}' "
                             "through '{owner_attr}' attribute"
                             .format(**locals()))

    def __inherit_attr(cls, attr, value):
        cls.__check_old_owner(value)

        value.__owner = cls, attr
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


def is_inherit_value(value):
    return getattr(value, 'auto_inherit', False)


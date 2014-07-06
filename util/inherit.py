"""
Dynamic inheritance for class members.
"""

from _compat import *
from util.itertools import pop_iter
from util.itertools import unique


class InheritMeta(type):

    def __bases_for_attr(cls, attr):
        base_values = dict()  # {id(base): value}

        check_owner = cls.__check_owner
        todo = list(cls.__bases__)
        for base in unique(pop_iter(todo)):
            if attr in base.__dict__:
                value = base.__dict__[attr]
                check_owner(attr, value, base)
                base_values[id(base)] = value
            else:
                todo += base.__bases__

        return [base_values[base_id] for base_id in map(id, cls.__mro__)
                if base_id in base_values]

    def __inherit_attr(cls, attr, value):
        if cls.__check_owner(attr, value) is None:
            value.__owner = cls, attr, value.__bases__
            try:
                value.__bases__ = cls.__bases_for_attr(attr)
            except:
                del value.__owner  # __bases__ is rolled back automatically
                raise

    def __uninherit_attr(cls, attr, value):
        orig_bases = cls.__check_owner(attr, value)
        if orig_bases is not None:
            value.__bases__ = orig_bases
            del value.__owner

    def __check_owner(cls, attr, value, target_cls=None):
        try:
            owner_cls, owner_attr, orig_bases = value.__owner
        except AttributeError:
            return

        if target_cls is None:
            target_cls = cls

        if target_cls is owner_cls and attr == owner_attr:
            return orig_bases

        raise ValueError("Can't inherit value '{value}' "
                         "already owned by '{owner_cls}' "
                         "through '{owner_attr}' attribute"
                         .format(**locals()))

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

    def mro(cls):
        cls.__check_base_metas(map(type, cls.__bases__))

        for attr, value in iteritems(cls.__dict__):
            if is_inherit_value(value):
                cls.__inherit_attr(attr, value)

        return super(InheritMeta, cls).mro()

    def __kick_mro_update(cls):
        type.__dict__['__bases__'].__set__(cls, cls.__bases__)

    def __setattr__(cls, attr, value):
        cls.__check_owner(attr, value)
        try:
            cls.__uninherit_attr(attr, cls.__dict__.get(attr))
            super(InheritMeta, cls).__setattr__(attr, value)
        finally:
            cls.__kick_mro_update()  # will find the value in cls.__dict__

    def __delattr__(cls, attr):
        try:
            cls.__uninherit_attr(attr, cls.__dict__.get(attr))
            super(InheritMeta, cls).__delattr__(attr)
        finally:
            cls.__kick_mro_update()


def is_inherit_value(value):
    return getattr(value, 'auto_inherit', False)


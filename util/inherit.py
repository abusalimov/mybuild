"""
Dynamic inheritance for class members.
"""

from _compat import *
from util.itertools import pop_iter
from util.itertools import unique


class InheritMeta(type):
    """
    Classes created with this metaclass manage their class attributes so that
    a value (with its 'inherit_self' attribute set to a truth) can inherit
    one from the same attribute of some base type.

    Let's create three classes using InheritMeta (owner classes): A, B, C

    >>> from util.inherit import InheritMeta
    >>> from _compat import *
    >>> class A(extend(metaclass=InheritMeta)):
    ...     pass
    ...
    >>> class B(A):
    ...     pass
    ...
    >>> class C(B):
    ...     pass
    ...

    Now define classes that are gonna be managed (value classes): X, Y, Z
    The __repr__ method of each class is overridden to emit its name along
    with a result of a super class, effectively resulting in a pretty-printed
    __mro__ chain.

    >>> class O(object):
    ...     inherit_self = True
    ...     __repr__ = lambda self: 'O'
    ...
    >>> class X(O):
    ...     __repr__ = lambda self: 'X -> ' + super(X, self).__repr__()
    ...
    >>> class Y(O):
    ...     __repr__ = lambda self: 'Y -> ' + super(Y, self).__repr__()
    ...
    >>> class Z(O):
    ...     __repr__ = lambda self: 'Z -> ' + super(Z, self).__repr__()
    ...

    Create an instance of each value class:

    >>> x, y, z = X(), Y(), Z()
    >>> x, y, z
    (X -> O, Y -> O, Z -> O)

    Now assigning the value classes to an attribute 'V' of the owner classes
    reflects on the inheritance hieararchy of the value classes:

    >>> A.V = X
    >>> x
    X -> O

    >>> B.V = Y
    >>> issubclass(Y, X)
    True
    >>> y
    Y -> X -> O

    >>> C.V = Z
    >>> issubclass(Z, Y)
    True
    >>> z
    Z -> Y -> X -> O

    >>> del B.V
    >>> issubclass(Z, Y)
    False
    >>> issubclass(Z, X)
    True
    >>> z
    Z -> X -> O

    Values don't necessarily need to be actual classes, an owner class in fact
    only manages __bases__ attribute of a value.

    """

    def __bases_for_attr(cls, attr, mro):
        base_values = dict()  # {id(base): value}

        check_owner = cls.__check_owner
        todo = list(cls.__bases__)
        for base in unique(pop_iter(todo)):
            if not hasattr(base, 'inherit_update_subclasses'):
                # Base is definitely not an instance of InheritMeta, nor
                # it provides a manual way to invoke refreshing of
                # auto-inheritance of its subclasses that support it.
                continue
            if attr in base.__dict__:
                value = base.__dict__[attr]
                check_owner(attr, value, base)
                base_values[id(base)] = value
            else:
                todo += base.__bases__

        return tuple(base_values[base_id] for base_id in map(id, mro)
                     if base_id in base_values)

    def __inherit_attr(cls, attr, value, mro):
        orig_bases = cls.__check_owner(attr, value)
        if orig_bases is None or cls.__mro__ != mro:
            if orig_bases is None:
                orig_bases = value.__bases__
            value.__owner = cls, attr, orig_bases

            attr_bases = cls.__bases_for_attr(attr, mro)
            rest_bases = tuple(base for base in orig_bases
                               if base not in attr_bases)
            try:
                value.__bases__ = attr_bases + rest_bases
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
        mro = super(InheritMeta, cls).mro()

        for attr, value in iteritems(cls.__dict__):
            if is_inherit_value(value):
                cls.__inherit_attr(attr, value, mro)

        return mro

    def inherit_update_subclasses(cls):
        """Assigning to __bases__ invokes mro() recalculation on the class
        and all of its direct and indirect sublcasses."""
        type.__dict__['__bases__'].__set__(cls, cls.__bases__)

    def __setattr__(cls, attr, value):
        cls.__check_owner(attr, value)
        try:
            cls.__uninherit_attr(attr, cls.__dict__.get(attr))
            super(InheritMeta, cls).__setattr__(attr, value)
            # inherit_update_subclasses will find the value in cls.__dict__
            # and perform the actual __inherit_attr on it.
        finally:
            cls.inherit_update_subclasses()

    def __delattr__(cls, attr):
        try:
            cls.__uninherit_attr(attr, cls.__dict__.get(attr))
            super(InheritMeta, cls).__delattr__(attr)
        finally:
            cls.inherit_update_subclasses()


def is_inherit_value(value):
    return getattr(value, 'inherit_self', False)


if __name__ == '__main__':
    import doctest
    doctest.testmod()

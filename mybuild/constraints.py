"""
Constraints represent a conjunction of modules an their options required by
a certain instance.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-09"

__all__ = ["Constraints", "ConstraintError"]


from itertools import izip
from operator import attrgetter

from core import *

import logs as log


class Constraints(object):
    __slots__ = '_dict'

    def __init__(self, _dict=None):
        super(Constraints, self).__init__()
        if _dict is None:
            _dict = IncrementalDict()
        self._dict = _dict

    def freeze(self):
        self.__class__ = FrozenConstraints

    def fork(self):
        if __debug__:
            self.freeze()
        return Constraints(self._dict.fork())

    def merge_children(self, children, update_parent=True):
        return self.merge(children, self, update_parent)

    @classmethod
    def merge(cls, children, until_parent=None, update_parent=True):
        log.debug('mybuild: parent=%r, merging %r', until_parent, children)

        parent_dict = until_parent._dict if until_parent is not None else None
        new_dict = IncrementalDict(parent_dict)

        for child in children:
            child.flatten(until_parent, update_parent)
            for key, value in child._dict.iteritems():
                if key in new_dict:
                    new_dict[key].update(value)
                else:
                    new_dict[key] = value.clone()

        return Constraints(new_dict)

    def flatten(self, until_parent=None, update_parent=True):
        self_dict = self._dict

        for parent_dict in self_dict.iter_parents(until_parent._dict,
                                                  update_parent):
            for key, value in parent_dict.iteritems():
                if key not in self_dict:
                    self_dict[key] = value.clone()

    def get(self, module, option=None):
        try:
            constraint = self._dict[module]
        except KeyError:
            raise ConstraintError('No decision is made yet')

        if option is None:
            return constraint.get()
        else:
            return constraint.get_option(option)

    def check(self, module, option=None, value=True):
        """
        Returns tristate: boolean for a definite answer, None otherwise.
        """
        try:
            constraint = self._dict[module]
        except KeyError:
            return None

        if option is None:
            return constraint.check(value)
        else:
            return constraint.check_option(option, value)

    def check_mslice(self, mslice):
        """
        Returns tristate: boolean for a definite answer, None otherwise.
        In case when answers for elements differ, precedence is the following:
            False -> None -> True (like for AND, but with None alternative)
        Undefined (Ellipsis) values of optuple are not considered.
        """
        try:
            constraint = self._dict[mslice._module]
        except KeyError:
            return None

        return constraint.check_mslice(mslice)

    def _constraint_for(self, module):
        self_dict = self._dict

        try: # retrieve a privately owned constraint
            constraint = self_dict[module]

        except KeyError: # if necessary, create it from scratch
            constraint = self_dict[module] = ModuleConstraint(module)

        else: # or clone it from a parent
            if module not in self_dict: # found in some parent
                constraint = self_dict[module] = constraint.clone()

        # Anyway, the 'constraint' is not shared with any other instance,
        # and we are free to modify it.

        return constraint

    def constrain(self, module, option=None, value=True, negated=False,
            fork=False):
        this = self if not fork else self.fork()

        constraint = this._constraint_for(module)

        if option is None:
            constraint.constrain(value, negated)
        else:
            constraint.constrain_option(option, value, negated)

        return this

    def constrain_mslice(self, mslice, negated=False, fork=False, atomic=True):
        # No need to care about atomicity if we are going to fork ourselves.
        atomic = atomic and not fork
        this = self if not fork else self.fork()

        constraint = this._constraint_for(mslice._module)

        constraint.constrain_mslice(mslice, negated, atomic)

        return this

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self._dict)


class FrozenConstraints(Constraints):
    """
    Constraints instance becomes frozen on fork to keep its children in a
    consistent state.
    """
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        raise InternalError('Attempting to instantiate FrozenConstraints')

    def constrain(self, module, option=None, value=True, negated=False,
            fork=False):
        if not fork:
            raise InternalError('Attempting to constrain frozen constraints '
                                'without forking')

        return Constraints.constrain(self, module, option, value, negated,
                                     fork=True)


class IncrementalDict(dict):
    """Delegates lookup for a missing key to the parent dictionary."""
    __slots__ = '_parent'

    parent = property(attrgetter('_parent'))

    def __init__(self, parent=None):
        dict.__init__(self)
        self._parent = parent

    def __missing__(self, key):
        """Looks up the parents chain for the key."""
        parent = self._parent
        while parent is not None:
            if key in parent:
                return parent[key]
            parent = parent._parent
        else:
            raise KeyError

    def fork(self):
        cls = type(self)
        return cls(parent=self)

    def iter_parents(self, until_parent=None, update_parent=False):
        parent = self._parent

        while parent is not until_parent:
            current = parent
            try:
                parent = parent._parent
            except AttributeError:
                assert parent is None
                raise InternalError("'until_parent' must be a parent "
                                    "of this dict")

            yield current

        if update_parent:
            self._parent = until_parent

    def __repr__(self):
        return (dict.__repr__(self) if self._parent is None else
                '%r <- %s' % (self._parent, dict.__repr__(self)))


class ConstraintBase(object):
    """A constraint holding a single value."""
    __slots__ = '_value'

    def __init__(self):
        super(ConstraintBase, self).__init__()
        self._value = Ellipsis

    def clone(self):
        cls = type(self)
        clone = cls.__new__(cls)
        clone._value = self._value
        return clone

    def update(self, other):
        other_value = other._value
        if other_value is not Ellipsis:
            self.constrain(other_value)

    def get(self):
        value = self._value
        if value is Ellipsis:
            raise ConstraintError('Decision about an exact value '
                                  'is not made yet')

        return value

    def check(self, other_value):
        value = self._value
        if value is not Ellipsis:
            return value == other_value

    def constrain(self, new_value):
        assert new_value is not Ellipsis

        old_value = self._value
        if old_value is not Ellipsis and old_value != new_value:
            raise ConstraintError('Reassigning already set value '
                                  'to a different one: %r != %r',
                                  old_value, new_value)

        self._value = new_value

    def __nonzero__(self):
        """
        Note truth value of a constraint only indicates whether it has
        been set or not, it tells nothing about the value itself.
        """
        return self._value is not Ellipsis

    def __repr__(self):
        value = self._value
        return '<[%r]>' % value if value is not Ellipsis else '<[?]>'


class ModuleConstraint(ConstraintBase):
    """ModuleConstraint vector."""
    __slots__ = '_options'

    def __init__(self, module):
        super(ModuleConstraint, self).__init__()
        optuple = module._options
        self._options = optuple._make(OptionConstraint() for _ in optuple)

    def clone(self):
        # Check for immutability.
        value = self._value
        if value is False:
            return self
        if value is True:
            for o in self._options:
                if o._value is Ellipsis:
                    break
            else:
                return self

        clone = super(ModuleConstraint, self).clone()
        clone._options = self._options._make(o.clone() for o in self._options)
        return clone

    def update(self, other):
        super(ModuleConstraint, self).update(other)

        for self_option, other_option in izip(self._options, other._options):
            self_option.update(other_option)

    def get_option(self, option):
        if self._value is False:
            raise ConstraintError('Getting an option '
                                  'of a definitely excluded module')
        return getattr(self._options, option).get()

    def check_option(self, option, other_value):
        if self._value is False:
            return False
        return getattr(self._options, option).check(other_value)

    def check_mslice(self, mslice):
        if self._value is False:
            return False

        check = True
        for value, constraint in mslice._izipwith(self._options):
            res = constraint.check(value)
            if res is not True:
                check = res
            if check is False:
                break

        return check

    def constrain_option(self, option, new_value, negated=False):
        if self._value is not False:
            getattr(self._options, option).constrain(new_value, negated)

        if not negated:
            self.constrain(True)

    def constrain_mslice(self, mslice, negated=False, atomic=True):
        option_constraints = tuple(mslice._izipwith(self._options, swap=True))

        if not option_constraints:
            self.constrain(True, negated)
            return

        if atomic:
            for constraint, value in option_constraints:
                if constraint.check(value) is negated:
                    constraint.constrain(value) # let it fall
                    assert False, "must not be reached"

        if not negated:
            self.constrain(True)

        for constraint, value in option_constraints:
            constraint.constrain(value)

    def constrain(self, new_value, negated=False):
        assert isinstance(new_value, bool)
        new_value ^= negated

        if self._value is not new_value:
            super(ModuleConstraint, self).constrain(new_value)
            if new_value is False:
                self._options = self._options._ellipsis

    def __nonzero__(self):
        return (super(ModuleConstraint, self).__nonzero__() or
                any(self._options))

    def __repr__(self):
        value = self._value

        string = repr(value) if value is not Ellipsis else '?'
        if value is not False:
            options_str = ', '.join('%s=%r' % (o,v)
                                    for o,v in self._options._iterpairs() if v)
            if options_str:
                string += ': %s' % options_str

        return '<[%s]>' % string


class OptionConstraint(ConstraintBase):
    """A constraint which supports additional exclusion set."""
    __slots__ = '_exclusion_set'

    def __init__(self):
        super(OptionConstraint, self).__init__()
        self._exclusion_set = None

    def clone(self):
        clone = super(OptionConstraint, self).clone()
        clone._exclusion_set = (self._exclusion_set and
                                self._exclusion_set.copy())
        return clone

    def constrain(self, value, negated=False):
        assert value is not Ellipsis

        if not negated:
            if self._exclusion_set is not None and \
                    value in self._exclusion_set:
                raise ConstraintError('Setting a new value '
                                      'which was previously excluded: %r',
                                      value)

            super(OptionConstraint, self).constrain(value)
            self._exclusion_set = None

        else: # negated, exclude the value

            if self._value is not Ellipsis:
                if self._value == value:
                    raise ConstraintError('Excluding an already set value: %r',
                                          value)
                return # no need to exclude

            if self._exclusion_set is None:
                self._exclusion_set = set()
            self._exclusion_set.add(value)

    def update(self, other):
        other_exclusion = other._exclusion_set
        if self._value is Ellipsis and other_exclusion is not None:

            self_exclusion = self._exclusion_set
            if self_exclusion is None:
                self_exclusion = self._exclusion_set = set()

            self_exclusion.update(other_exclusion)

        super(OptionConstraint, self).update(other)

    def check(self, value):
        ret = super(OptionConstraint, self).check(value)

        return False if (ret is None and
                         self._exclusion_set is not None and
                         value in self._exclusion_set) else ret

    def __nonzero__(self):
        return (super(OptionConstraint, self).__nonzero__() or
                bool(self._exclusion_set))

    def __repr__(self):
        return '<[~%r]>' % self._exclusion_set if self._exclusion_set else \
            super(OptionConstraint, self).__repr__()


class ConstraintError(InstanceError):
    """
    InstanceError subclass raised in case when the reason of an error is
    constraints violation.
    """


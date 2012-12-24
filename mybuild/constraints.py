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
from chaindict import ChainDict

import logs as log

from instance import InstanceError

class TreeNode(object):
    """docstring for TreeNode"""
    __slots__ = '__base', '__branches'

    base = property(attrgetter('_'+'TreeNode'+'__base'))

    def __init__(self, base=None):
        super(TreeNode, self).__init__()

        self.__base = None
        self.__branches = None

        self._set_base(base)

    def new_branch(self):
        cls = type(self)
        return cls(base=self)

    def _set_base(self, new_base):
        old_base = self.__base

        if new_base is old_base:
            return

        if old_base is not None:
            old_base.__branches.remove(self)

        self.__base = new_base

        if new_base is not None:
            sublings = new_base.__branches
            if sublings is None:
                sublings = new_base.__branches = set()
            sublings.add(self)

    def prune(self):
        branches = self.__branches
        if branches:
            for branch in branches.copy():
                branch.prune()

        self._set_base(None)

    def has_branches(self):
        return bool(self.__branches)

    def iter_branches(self):
        return iter(self.__branches or ())

    @property
    def sole_branch(self):
        branches = self.__branches
        if branches is None or len(branches) != 1:
            return None

        return iter(branches).next()

    def reintegrate_sole_branch(self):
        branch = self.sole_branch
        if branch is None:
            return None

        sub_branches = branch.__branches

        if sub_branches is not None:
            for sub_branch in sub_branches:
                sub_branch.__base = self

            self.__branches = sub_branches

        else:
            self.__branches.clear()

        branch.__base = None
        branch.__branches = None

        return branch


class Constraints(TreeNode):
    """Knowledge base on presence of certain modules and their options.

    This class is designed to accumulate module requirements, providing various
    operations on specifying, checking and getting constrained values. See
    'constrain', 'check' and 'get' methods respectively, with their
    derivatives.

    Constraints object is responsible for tracking and preventing value
    conflicts, thus keeping itself in a consistent state. For example, once a
    client has excluded a certain module, he cannot then specify a value for
    some option belonging to this module.

    Modifying constraints object is a one-way action, that is once a constraint
    has been set (committed) no one can undo it. Moreover, if such action
    results in a constraints violation, the whole object is considered dead and
    becomes unusable, i.e. no conflict resolution or rollback is performed.

    Constraints are organized into a tree, where branches extend the base and
    hold more precise or strict requirements. Once a new branch of a
    constraints object is created the object is sealed for further
    modifications. In other words, only leaves of the tree are mutable, other
    nodes are read-only, that prevents possible conflicts with their branches.
    A branch can be removed (prunned) from the tree irreversibly destroying
    each node of the branch. A leaf is automatically prunned in case of
    constraints violation when modifying it.
    """
    __slots__ = '_modules', '_frozen'

    def __init__(self, base=None, _dict=None):
        super(Constraints, self).__init__(base)

        base_dict = base._modules if base is not None else None
        if _dict is None:
            _dict = ChainDict(base_dict)
        assert _dict.base is base_dict

        self._modules = _dict
        self._frozen = False

    def freeze(self):
        """Seal the object forever. Prevents any further modifications."""
        self._frozen = True

    def is_frozen(self):
        return self._frozen

    def can_change(self):
        return not self.is_frozen() and not self.has_branches()

    def is_alive(self):
        """Tells whether the object is still usable."""
        return True

    def prune(self):
        """Prevents further usage of the object.

        After calling this method 'is_alive' will always return False.
        """
        super(Constraints, self).prune()
        self._kill()

    def _kill(self):
        """Deletes slot attributes to prevent further using of the object."""
        del self._modules
        self.__class__ = DeadConstraints

    def new_branch(self, freeze=False):
        """
        Create a new Constraints object with its 'base' set to this one.
        """
        if freeze:
            self.freeze()
        return super(Constraints, self).new_branch()

    def reintegrate_sole_branch(self):
        """
        In case when this object has only one branch the latter is detached
        from the tree and its contents is merged into this. After reintegrating
        the branch becomes unusable and must not be referenced anymore.
        Returns the sole branch (gutted), if any, None otherwise.
        """
        sole_branch = super(Constraints, self).reintegrate_sole_branch()

        if sole_branch is not None:
            self_dict = self._modules
            self_dict.update(sole_branch._modules)

            for new_branch in self.iter_branches():
                new_branch._modules.base = self_dict

            sole_branch._kill()

        return sole_branch

    def merge_children(self, branches):
        """See 'Constraints.merge' method.
        The resulting Constraints object becomes a new branch of this object.
        """
        return self.merge(branches, self)

    @classmethod
    def merge(cls, branches, stop_base=None):
        """
        Merges the given branches into a single Constraints object which
        becomes a new direct branch of 'stop_base'.

        Args:
            branches:
                Iterable containing objects of Constraints type. Each given
                branch must be a child (either direct or indirect) of
                'stop_base', if any, otherwise an error is raised.
            stop_base (Constraints):
                Common base of each of branches.

        Raises:
            ConstraintViolationError:
                In case of conflicts between children.
            InternalError:
                If one of the branches is not actually a child of the
                'stop_base'.

        Returns:
            A new Constraints object whichs base is set to 'stop_base'.
        """
        log.debug('mybuild: base=%r, merging %r', stop_base, branches)

        def to_flat_dict(from_dict, to_dict):
            def iter_dict_chain():
                yield from_dict
                for e in from_dict.iter_base_chain():
                    if e is to_dict:
                        break
                    yield e
                else:
                    if to_dict is not None:
                        raise InternalError(
                            "'stop_base' must be a base of this")

            ret_dict = {}
            for a_dict in reversed(iter_dict_chain()):
                ret_dict.update(a_dict)

            return ret_dict

        base_dict = stop_base._modules if stop_base is not None else None
        new_dict = ChainDict(base_dict)

        for child in branches:
            child_dict = child._modules
            for key, value in to_flat_dict(child_dict, base_dict).iteritems():
                if key in new_dict:
                    new_dict[key].update(value)
                else:
                    new_dict[key] = value.clone()

        return cls(stop_base, _dict=new_dict)

    def get(self, module, option=None):
        try:
            constraint = self._modules[module]
        except KeyError:
            raise ConstraintError('No constraints on this module')

        if option is None:
            return constraint.get()
        else:
            return constraint.get_option(option)

    def check(self, module, option=None, value=Ellipsis):
        """
        Returns:
            Tristate - boolean for a definite answer, None otherwise.
        """
        try:
            constraint = self._modules[module]
        except KeyError:
            return None

        if option is None:
            return constraint.check(True)
        else:
            return constraint.check_option(option, value)

    def check_mslice(self, mslice):
        """
        Returns:
            Tristate - boolean for a definite answer, None otherwise.
            In case when answers for elements differ, precedence is from
            negative through indefinite to positive, that is like for AND, but
            with None alternative:
                False -> None -> True
        Note:
            Undefined (Ellipsis) values of optuple are not considered.
        """
        try:
            constraint = self._modules[mslice._module]
        except KeyError:
            return None

        return constraint.check_mslice(mslice)

    def constrain(self, module, option=None, value=Ellipsis, negated=False,
            branch=False, dry_run=False):
        """Adds a new constraint.

        If only a 'module' argument is given, constrains the module presence.
        In case when an 'option' is not None, a 'value' must also be specified.

        Args:
            module (Module):
                The module to work with.
            option (str):
                The name of one of the module's options (optional).
            value:
                Used only if the option is specified too (optional).
            negated (bool):
                Tells whether the meaning of the operation should be inverted,
                that is for excluding modules or options.
            branch (bool):
                Whether to create a new branch or to constrain the current
                object itself.
            dry_run (bool):
                Performs only checks for violation, no constraints are actually
                get modified. In case of an error behaves as usual.

        Raises:
            ConstraintViolationError:
                In case of conflicts with existing constraints. Note that once
                such error is raised the object becomes totally destroyed and
                must not be used anymore. See 'Constraints.prune' method.

        Returns:
            The actual Constraints object that was used,
            that is self if 'branch' is False, or a branch of self otherwise.

        """
        assert branch or self.can_change()

        this = self if not branch else self.new_branch()

        constraint = this._constraint_for(module, dry_run)

        try:
            if option is None:
                constraint.set(not negated)
            else:
                constraint.set_option(option, value, negated)

        except ConstraintViolationError:
            this.prune()
            raise

        return this

    def _constraint_for(self, module, dry_run=False):
        """Retrieves a privately owned constraint for the given module."""
        assert self.can_change()

        self_dict = self._modules
        store_constraint = None

        try:
            constraint = self_dict[module]

        except KeyError: # if necessary, create it from scratch
            constraint = store_constraint = ModuleConstraint(module)

        else: # or clone it from a base
            if module not in self_dict: # found in some base
                constraint = store_constraint = constraint.clone()

        if not dry_run and store_constraint is not None:
            self_dict[module] = store_constraint

        # Anyway, the 'constraint' is not shared with any other instance,
        # and we are free to modify it.

        return constraint

    def constrain_mslice(self, mslice, branch=False, dry_run=False):
        """
        Much like a plain 'Constraints.constrain' method, but works with a
        whole mslice at a time.
        """
        assert branch or self.can_change()

        this = self if not branch else self.new_branch()

        this.constrain(mslice._module, dry_run=dry_run)
        for option, value in mslice._iterpairs():
            this.constrain(mslice._module, option, value, dry_run=dry_run)

        return this

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self._modules)

class DeadConstraints(Constraints):
    __slots__ = ()

    def __metaclass__(name, bases, attrs):
        def stub_for(attr):
            def stub(self):
                raise InternalError('Referencing %s on %r' % (attr, self))
            return stub

        for a in dir(Constraints):
            if not a.startswith('_') and a not in attrs:
                attrs[a] = property(stub_for(a))

        return type(name, bases, attrs)

    def __new__(cls, *args, **kwargs):
        raise InternalError('Instantiating %s' % cls.__name__)

    def __repr__(self):
        return object.__repr__(self)

    def is_alive(self):
        return False


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

    def update(self, other, dry_run=False):
        other_value = other._value
        if other_value is not Ellipsis:
            self.set(other_value, dry_run)

    def get(self):
        value = self._value
        if value is Ellipsis:
            raise ConstraintError(
                'Decision about an exact value is not made yet')

        return value

    def check(self, other_value):
        assert other_value is not Ellipsis

        value = self._value
        if value is not Ellipsis:
            return value == other_value

    def set(self, new_value, dry_run=False):
        assert new_value is not Ellipsis

        old_value = self._value
        if old_value is not Ellipsis and old_value != new_value:
            raise ConstraintViolationError(
                'Reassigning already set value to a different one: %r != %r',
                old_value, new_value)

        if not dry_run:
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

        options = module._options
        self._options = options._make(OptionConstraint() for _ in options)

        # if mslice is None:
        #     mslice = module._options._ellipsis
        # else:
        #     assert module is mslice._module
        #     self.set(True)

        # self._options = mslice._make(OptionConstraint(v) for v in mslice)

    def clone(self):
        # Check for immutability.
        value = self._value
        if value is True:
            for o in self._options:
                if o._value is Ellipsis:
                    break
            else:
                return self
        elif value is False:
            return self

        clone = super(ModuleConstraint, self).clone()
        clone._options = self._options._make(o.clone() for o in self._options)
        return clone

    def update(self, other, dry_run=False):
        super(ModuleConstraint, self).update(other, dry_run)

        if self._value is not False:
            for option, other_option in izip(self._options, other._options):
                option.update(other_option, dry_run)

    def get_option(self, option):
        if self._value is False:
            raise ConstraintError(
                'Getting an option of a definitely excluded module')
        return getattr(self._options, option).get()

    def check_option(self, option, other_value):
        if self._value is False:
            return False
        return getattr(self._options, option).check(other_value)

    def check_mslice(self, mslice):
        if self._value is False:
            return False

        check = True
        for constraint, value in mslice._izipwith(self._options, swap=True):
            res = constraint.check(value)
            if res is not True:
                check = res
            if check is False:
                break

        return check

    def set_option(self, option, new_value, negated=False, dry_run=False):
        if self._value is not False:
            option = getattr(self._options, option)
            set_option = option.set if not negated else option.set_negated
            set_option(new_value, dry_run)

        if not negated:
            self.set(True, dry_run)

    def set(self, new_value, dry_run=False):
        assert isinstance(new_value, bool)

        if self._value is not new_value:
            super(ModuleConstraint, self).set(new_value, dry_run)
            if not dry_run and new_value is False:
                self._options = self._options._ellipsis  # to catch stupid bugs

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
    """A constraint which supports additional negation set."""
    __slots__ = '_negation_set'

    def __init__(self, value=Ellipsis):
        super(OptionConstraint, self).__init__()
        self._negation_set = None

        if value is not Ellipsis:
            self.set(value)

    def clone(self):
        clone = super(OptionConstraint, self).clone()
        clone._negation_set = (self._negation_set and
                                self._negation_set.copy())
        return clone

    def set(self, value, dry_run=False):
        assert value is not Ellipsis

        if self._negation_set is not None and value in self._negation_set:
            raise ConstraintViolationError(
                'Setting a new value which was previously excluded: %r',
                value)

        super(OptionConstraint, self).set(value, dry_run)
        if not dry_run:
            self._negation_set = None

    def set_negated(self, value, dry_run=False):
        assert value is not Ellipsis

        if self._value is not Ellipsis:
            if self._value == value:
                raise ConstraintViolationError(
                    'Excluding an already set value: %r', value)

        elif not dry_run:
            if self._negation_set is None:
                self._negation_set = set()
            self._negation_set.add(value)

    def update(self, other, dry_run=False):
        if not dry_run:
            other_negation = other._negation_set
            if self._value is Ellipsis and other_negation is not None:

                self_negation = self._negation_set
                if self_negation is None:
                    self_negation = self._negation_set = set()

                self_negation.update(other_negation)

        super(OptionConstraint, self).update(other, dry_run)

    def check(self, value):
        ret = super(OptionConstraint, self).check(value)

        return False if (ret is None and
                         self._negation_set is not None and
                         value in self._negation_set) else ret

    def __nonzero__(self):
        return (super(OptionConstraint, self).__nonzero__() or
                bool(self._negation_set))

    def __repr__(self):
        return ('<[~%r]>' % self._negation_set if self._negation_set else
                super(OptionConstraint, self).__repr__())


class NotifyingConstraints(Constraints):
    """
    NotifyingConstraints supports relatively efficient modifying of an
    arbitrary node of the constraints tree, even non-leaf. It also provides
    facilities for notifying listeners about prunning of interesting branches.
    """
    __slots__ = '_root_modules'

    def __init__(self, base=None):
        super(NotifyingConstraints, self).__init__(base)

        self._root_modules = base._root_modules if base is not None else {}
        if self._modules.base is None:
            self._modules.base = self._root_modules

    def prune(self):
        self_dict = self._modules

        super(NotifyingConstraints, self).prune()

        for constraint in self_dict.itervalues():
            constraint.prune()

    def _constraint_for(self, module, dry_run=False):
        if dry_run:
            return super(NotifyingConstraints, self)._constraint_for(
                self, module, dry_run)

        raise NotImplementedError
        # self_dict = self._modules
        # root_dict = self._root_modules
        # new_proxy = NotifyingModuleConstraintProxy

        # try:
        #     constraint = self_dict[module]

        # except KeyError:
        #     constraint = root_dict[module] = new_proxy(self)

        # if module not in self_dict:
        #     constraint = self_dict[module] = new_proxy(self, base=constraint)

        return constraint

class NotifyingModuleConstraintProxy(TreeNode):
    """
    Provides ModuleConstraint-like interface also maintaining the state of
    branches, if any.
    """
    __slots__ = '_owner', '_target'

    _value   = property(attrgetter('_target._value'))
    _options = property(attrgetter('_target._options'))

    def __init__(self, owner, base=None, module=None):
        super(NotifyingModuleConstraintProxy, self).__init__(base)
        self._owner = owner

        if base is not None:
            self._target = base._target.clone()
        elif module is not None:
            self._target = ModuleConstraint(module)
        else:
            raise InternalError("Either 'base' or 'module' must be specified")

    def clone(self):
        raise InternalError('Cloning proxy constraint')

    def _modify(self, fxn, dry_run, _silent=False):
        """
        Args:
            fxn (func(target, dry_run)):
                Modifier function which takes the following arguments:
                    target (ConstraintBase):
                        A target constraint object.
                    dry_run (bool):
                        Whether to perform real changes (False) or not (True).
                The function returns nothing, and may throw
                ConstraintViolationError.
        """
        try:
            fxn(self, dry_run)

        except ConstraintViolationError:
            self._owner.prune()  # it will re-invoke our prune()
            if not _silent:
                raise

        else:
            for branch in self.iter_branches():
                branch._modify(other, dry_run=True, _silent=True)

    def update(self, other, dry_run=False):
        other_target = other._target
        self._modify(lambda target, dry_run:
                     target.update(other_target, dry_run), dry_run)

    def set(self, new_value, dry_run=False):
        self._modify(lambda target, dry_run:
                     target.set(new_value, dry_run), dry_run)

    def set_option(self, option, new_value, negated=False, dry_run=False):
        self._modify(lambda target, dry_run:
                     target.set(option, new_value, negated, dry_run), dry_run)

    get        = property(attrgetter('_target.get'))
    get_option = property(attrgetter('_target.get_option'))

    check        = property(attrgetter('_target.check'))
    check_option = property(attrgetter('_target.check_option'))
    check_mslice = property(attrgetter('_target.check_mslice'))

    __nonzero__ = lambda self: self._target.__nonzero__()
    __repr__    = lambda self: self._target.__repr__()


class ConstraintError(InstanceError):
    """Base class for constraints-related errors."""

class ConstraintViolationError(ConstraintError):
    """Fatal error which leads to dectruction of a Constraints object.

    Raised in case when the reason of an error is constraints violation.
    """


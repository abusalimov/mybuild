"""
Mybuild core.

Author: Eldar Abusalimov
Date: Sep 2012

TODO docs. -- Eldar
"""

from collections import namedtuple
from contextlib import contextmanager
from functools import partial
from functools import update_wrapper
from functools import wraps
from inspect import getargspec
from itertools import chain
from itertools import imap
from itertools import izip
from itertools import product
from itertools import repeat
from operator import attrgetter
from traceback import print_exc
from traceback import print_stack

from expr import *
from util import singleton

import logs as log


class Module(object):
    """A basic building block of Mybuild."""

    class Type(object):
        """Base (marker) class for per-module types.

        Do not inherit or instantiate directly.
        """
        __slots__ = ()

        # These may be too strict checks, but it is OK,
        # since types are mapped to their modules one-to-one.
        _type_eq   = classmethod(lambda cls, other: cls is type(other))
        _type_hash = classmethod(id)

        def __eq__(self, other):
            return self._type_eq(type(other))
        def __hash__(self):
            return self._type_hash()

    _types = {} # attr-to-type

    @classmethod
    def register_type(cls, attr):
        """Deco maker for per-module classes."""

        if not isinstance(attr, basestring):
            raise TypeError("Attribure name must be a string, "
                            "got %s object instead: %r" % (type(attr), attr))

        if not attr.startswith('_'):
            raise ValueError("Attribure name must start with an underscore")

        def deco(target):
            if not isinstance(target, type):
                raise TypeError("'@%s.register_type(...)' must be applied "
                                "to a class, got %s object instead: %r" %
                                (cls.__name__, type(target), target))

            if not hasattr(target, '_new_type'):
                raise TypeError("'@%s.register_type(...)'-decorated class "
                                "must define a '_new_type' classmethod" %
                                (cls.__name__,))

            if hasattr(cls, attr) or attr in cls._types:
                raise ValueError("%s class already has attribure '%s'" %
                                 (cls.__name__, attr))

            cls._types[attr] = target

            return target

        return deco

    def __init__(self, fxn):
        super(Module, self).__init__()

        self._name = fxn.__name__
        module_type = type('Module_M%s' % (self._name,),
                           (self.Type,),
                           dict(__slots__=(),
                                _module=self,
                                _module_name=self._name))

        for attr, cls in self._types.iteritems():
            setattr(self, attr, cls._new_type(module_type, fxn))

    _options = property(attrgetter('_optuple_type._fields'))

    def __call__(self, **kwargs):
        return self._optuple_type._ellipsis._replace(**kwargs)

    def _to_optuple(self):
        return self._optuple_type._ellipsis

    def _to_expr(self):
        return self._atom

    def __repr__(self):
        return '%s(%s)' % (self._name, ', '.join(self._options))

def module(fxn):
    return update_wrapper(Module(fxn), fxn)

@Module.register_type('_atom')
class _ModuleAtom(Atom):
    """Module-bound atom."""
    __slots__ = ('_module',)

    def __init__(self, module):
        super(_ModuleAtom, self).__init__()
        self._module = module

    def eval(self, fxn, *args, **kwargs):
        ret = fxn(self._module, *args, **kwargs)
        return self if ret is None else ret

    def __repr__(self):
        return '%s' % (self._module._name,)

    @classmethod
    def _new_type(cls, module_type, *args):
        return cls(module_type._module)

@Module.register_type('_optuple_type')
class _Optuple(Module.Type):
    """Option tuple mixin type."""
    __slots__ = ()

    def _iter(self, with_ellipsis=False):
        return (iter(self) if with_ellipsis else
                (v for v in self if v is not Ellipsis))

    def _iterpairs(self, with_ellipsis=False):
        return self._izipwith(self._fields, with_ellipsis, swap=True)

    def _izipwith(self, other, with_ellipsis=False, swap=False):
        it = izip(self, other) if not swap else izip(other, self)
        self_idx = int(bool(swap))
        return (it if with_ellipsis else
                (pair for pair in it if pair[self_idx] is not Ellipsis))

    def _to_optuple(self):
        return self

    def __repr__(self):
        return '%s(%s)' % (self._module._name,
                           ', '.join('%s=%r' % pair
                                     for pair in self._iterpairs()))

    def __eq__(self, other):
        return self._type_eq(other) and tuple.__eq__(self, other)
    def __hash__(self):
        return self._type_hash() ^ tuple.__hash__(self)

    def _to_expr(self):
        option_atoms = tuple(A(v) for v,A in self._izipwith(self._atom_types))
        return (And._from_iterable(option_atoms) if option_atoms else
                self._module._to_expr())

    @classmethod
    def _options_defaults_from_fxn(cls, fxn):
        """Converts a function argspec into a (options, defaults) tuple."""

        args, va, kw, defaults = getargspec(fxn)
        defaults = defaults or ()

        if va is not None:
            raise TypeError(
                'Arbitrary arguments are not supported: *%r' % va)
        if kw is not None:
            raise TypeError(
                'Arbitrary keyword arguments are not supported: **%r' % kw)

        if not args:
            raise TypeError(
                'Module function must accept at least one argument')
        if len(args) == len(defaults):
            raise TypeError(
                'The first argument cannot have a default value: %r' % args[0])

        options = args[1:]
        for o in options:
            if not isinstance(o, basestring):
                raise TypeError(
                    'Tuple parameter unpacking is not supported: %r' % o)
            if o.startswith('_'):
                raise TypeError(
                    'Option name cannot start with an underscore: %r' % o)

        head_defaults = repeat((), len(options)-len(defaults))
        tail_defaults = ((v, not v) if isinstance(v, bool) else (v,)
            for v in defaults)
        defaults = tuple(chain(head_defaults, tail_defaults))

        return options, defaults

    @classmethod
    def _new_type(cls, module_type, fxn):
        options, defaults = cls._options_defaults_from_fxn(fxn)
        assert len(options) == len(defaults)

        optype_base = namedtuple('_OptupleBase', options)

        bogus_attrs = set(a for a in dir(optype_base)
            if not a.startswith('_'))
        bogus_attrs.difference_update(options)

        for attr in bogus_attrs:
            setattr(optype_base, attr, property())

        new_type = type('Optuple_M%s' % (module_type._module_name,),
                        (cls, optype_base, module_type),
                        dict(__slots__=()))

        new_type._defaults = new_type._make(defaults)
        new_type._ellipsis = new_type._make(repeat(Ellipsis, len(options)))
        new_type._atom_types = \
            new_type._make(_OptionAtom._new_type(module_type, o)
                           for o in options)

        optype_base._fields = new_type._make(options)

        return new_type

class _OptionAtom(Module.Type, Atom):
    """A single bound option."""
    __slots__ = ('_value')

    value  = property(attrgetter('_value'))
    option = property(attrgetter('_option'))

    def __init__(self, value):
        super(_OptionAtom, self).__init__()
        self._value = value

    def __eq__(self, other):
        return self._type_eq(other) and self._value == other._value
    def __hash__(self):
        return self._type_hash() ^ hash(self._value)

    def eval(self, fxn, *args, **kwargs):
        ret = fxn(self._module, option=self._option, value=self.value,
                *args, **kwargs)
        return self if ret is None else ret

    @classmethod
    def _replace(cls, new_value):
        return cls(new_value)

    @classmethod
    def _new_type(cls, module_type, option):
        return type('OptionAtom_M%s_O%s' % (module_type._module_name, option),
                    (cls, module_type),
                    dict(__slots__=(), _option=option))

    def __repr__(self):
        return '%s(%s=%r)' % (self._module._name, self._option, self._value)


class IncrementalDict(dict):
    """Delegates lookup for a missing key to the parent dictionary."""
    __slots__ = ('_parent',)

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


class Constraints(object):
    __slots__ = ('_dict',)

    def __init__(self, _dict=None):
        super(Constraints, self).__init__()
        if _dict is None:
            _dict = IncrementalDict()
        self._dict = _dict

    def freeze(self):
        self.__class__ = FrozenConstraints

    def fork(self):
        self.freeze()
        return Constraints(self._dict.fork())

    def merge_children(self, children, update_parent=True):
        log.debug('mybuild: parent=%r, merging %r', self, children)

        self_dict = self._dict
        new_dict = self_dict.fork()

        for child in children:
            child.flatten(self, update_parent)
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
            for key, value in parent.iteritems():
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

    def constrain(self, module, option=None, value=True, negated=False,
            fork=False):
        self = self if not fork else self.fork()
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

        if option is None:
            constraint.constrain(value, negated)
        else:
            constraint.constrain_option(option, value, negated)

        return self

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


class ConstraintBase(object):
    """A constraint holding a single value."""
    __slots__ = ('_value',)

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
            self._set(other_value)

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
    __slots__ = ('_options')

    options = property(attrgetter('_options'))
    _module = property(attrgetter('_options._module'))

    def __init__(self, module):
        super(ModuleConstraint, self).__init__()
        optuple = module._optuple_type._ellipsis
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
        if self._value is not False:
            return getattr(self._options, option).check(other_value)

    def constrain_option(self, option, new_value, negated=False):
        if not negated:
            self.constrain(True)

        if self._value is not False:
            getattr(self._options, option).constrain(new_value, negated)

    def constrain(self, new_value, negated=False):
        assert isinstance(new_value, bool)
        new_value ^= negated

        if self._value is not new_value:
            super(ModuleConstraint, self).constrain(new_value)
            if new_value is False:
                self._options = self._options._ellipsis

    def __nonzero__(self):
        return (super(ModuleConstraint, self).__nonzero__() or
                bool(self._options))

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
    __slots__ = ('_exclusion_set',)

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


class Error(Exception):
    """Base class for errors providing a logging-like constructor."""

    def __init__(self, msg, *args, **kwargs):
        if not isinstance(msg, basestring):
            raise TypeError("'msg' argument must be a string")
        if args and kwargs:
            raise TypeError('At most one of args or kwargs can be specified '
                            'at once, not both of them')

        super(Error, self).__init__(msg, args or kwargs or None)

    def __str__(self):
        msg, fmt_args = self.args
        return msg % fmt_args if fmt_args else msg

    def __repr__(self):
        msg, fmt_args = self.args
        type_name = type(self).__name__

        if not fmt_args:
            return '%s(%r)' % (type_name, msg)

        return '%s(%r, %s%r)' % (type_name, msg,
                                 '**' if isinstance(fmt_args, dict) else '*',
                                 fmt_args)

class InstanceError(Error):
    """
    Throwing this kind of errors from inside a module function indicates that
    instance is not viable anymore and thus shouldn't be considered.
    """

class ConstraintError(InstanceError):
    """
    InstanceError subclass raised in case when the reason of an error is
    constraints violation.
    """


class InternalError(Exception):
    """Unrecoverable application errors indicating that goes really wrong."""


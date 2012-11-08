"""
Mybuild core.

Author: Eldar Abusalimov
Date: Sep 2012

TODO docs. -- Eldar
"""

from collections import defaultdict
from collections import deque
from collections import MutableSet
from collections import namedtuple
from contextlib import contextmanager
from functools import partial
from functools import update_wrapper
from functools import wraps
from inspect import getargspec
from itertools import chain
from itertools import imap
from itertools import izip
from itertools import izip_longest
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

    def __init__(self, init_fxn):
        super(Module, self).__init__()

        self._name = init_fxn.__name__
        module_type = type('Module_M%s' % (self._name,), (self.Type,),
            dict(__slots__=(), _module=self, _module_name=self._name))

        self._instance_type = _Instance._new_type(module_type, init_fxn)
        self._optuple_type = _Optuple._new_type(module_type,
            *self._options_defaults_from_fxn(init_fxn))

        self._atom = _ModuleAtom(self)

    _options = property(attrgetter('_optuple_type._fields'))

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
    def _new_type(cls, module_type, options, defaults):
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


class _Instance(Module.Type):
    """docstring for _Instance"""

    class _InstanceProxy(object):
        """docstring for _InstanceProxy"""
        __slots__ = ('_owner_instance', '_optuple')

        def __init__(self, owner_instance, optuple):
            super(_Instance._InstanceProxy, self).__init__()
            self._owner_instance = owner_instance
            self._optuple = optuple

        def __nonzero__(self):
            return self._owner_instance._decide(self._optuple)

        def __getattr__(self, attr):
            if attr.startswith('_'):
                return object.__getattr__(attr)

            return self._owner_instance._decide_option(self._optuple, attr)

    def __init__(self, build_ctx, optuple, constraints):
        """Private constructor. Use '_post_new' instead."""
        super(_Instance, self).__init__()

        self._build_ctx = build_ctx
        self._optuple = optuple
        self._constraints = constraints

        with log.debug("mybuild: new %r", self):
            try:
                self._init_fxn(*optuple)
            except InstanceError as e:
                log.debug("mybuild: unviable %r: %s", self, e)
                raise e
            else:
                log.debug("mybuild: succeeded %r", self)

    @classmethod
    def _post_new(cls, build_ctx, optuple, _constraints=None):
        if _constraints is None:
            _constraints = Constraints()

        def new():
            try:
                instance = cls(build_ctx, optuple, _constraints)
            except InstanceError:
                pass
            else:
                build_ctx.register(instance)

        build_ctx.post(new)

    def ask(self, mslice):
        optuple = mslice._to_optuple()
        self._build_ctx.consider(optuple)
        return self._InstanceProxy(self, optuple)

    @singleton
    class _build_visitor(ExprVisitor):

        def visit(self, expr, constraints):
            expr = exprify(expr)
            log.debug('mybuild: visit [%r] %r with %r',
                      type(expr), expr, constraints)
            return ExprVisitor.visit(self,
                exprify_eval(expr, constraints.check), constraints)

        def visit_bool(self, expr, constraints):
            return (constraints,) if expr else ()

        def visit_Atom(self, expr, constraints, negated=False):
            try:
                expr.eval(constraints.constrain, negated=negated)
            except ConstraintError:
                return self.visit_bool(False, constraints)
            else:
                return self.visit_bool(True, constraints)

        def visit_Not(self, expr, constraints):
            return self.visit_Atom(expr.atom, constraints, negated=True)

        def visit_Or(self, expr, constraints):
            # disjuncion of disjunctions: (C1|C2) | ... | (CK|...|CN)
            # nothing special to do here, expand parens by flattening the list
            return tuple(chain.from_iterable(
                self.visit(e, constraints.fork()) for e in expr.operands))

        def visit_And(self, expr, constraints):
            # Important assumption:
            # 'expr.operands' first yields atomic expressions (atoms and
            # negations), and then compounds (disjunctions in this case).
            # This allows us to defer forking the 'constraints' as much as
            # possible, until it becomes really necessary.

            # conjuction of disjunctions: (C1|C2) & ... & (CK|...|CN)
            cj_of_djs = (self.visit(e, constraints) for e in expr.operands)

            # expand parens by merging constraint dicts to get the resulting
            # disjunction: C1&...&CK | C1&...&CN | C2&...&CK | C2&...&CN | ...
            def iter_multiply(djs):
                def uniquify_filter(djs):
                    """
                    Removes duplicates, filters out the parent constraints,
                    and yields non-empty iterables.
                    """
                    for dj in djs:
                        if not dj:
                            raise ConstraintError
                        if len(dj) == 1:
                            if dj[0] is not constraints:
                                yield dj
                        else:
                            constraints_by_id = dict((id(c), c) for c in dj)
                            del constraints_by_id[constraints]
                            if constraints_by_id:
                                yield constraints_by_id.itervalues()

                try:
                    djs_list = sorted(uniquify_filter(djs), key=len)
                except ConstraintError:
                    return

                if not djs_list:
                    yield constraints
                    return

                for new_cj in product(*djs_list):
                    try:
                        yield constraints.merge_children(new_cj)
                    except ConstraintError:
                        pass

            return tuple(iter_multiply(cj_of_djs))

    def _log_build_choices(self, name, choices):
        length = len(choices)
        log.debug('mybuild: got %d %s choice%s: %r',
            length, name, 's' if length != 1 else '', choices)

    def constrain(self, expr):
        with log.debug('mybuild: constrain %r', expr):
            choices = self._build_visitor.visit(expr, self._constraints)
            self._log_build_choices('constrain', choices)

            self._constraints = self._take_one_spawn_rest(choices)

    def _decide(self, expr):
        expr = exprify(expr)

        with log.debug('mybuild: deciding bool(%r)', expr):
            visit = self._build_visitor.visit

            yes_choices = visit(expr, self._constraints.fork())
            self._log_build_choices('"yes"', yes_choices)

            no_choices = visit(~expr, self._constraints.fork())
            self._log_build_choices('"no"', no_choices)

            ret = bool(yes_choices)
            choices = no_choices, yes_choices

            self._constraints = self._take_one_spawn_rest(choices[ret])
            self._spawn_all(choices[not ret])

            log.debug('mybuild: return %s', ret)
            return ret

    def _decide_option(self, optuple, option):
        module = optuple._module

        with log.debug('mybuild: deciding %r.%s', optuple, option):
            if not hasattr(optuple, option):
                raise AttributeError("'%s' module has no attribute '%s'" %
                    (module._name, option))

            try:# to get an already constrained exact value (if any).
                # This is the way of how spawned instances get an option
                # which caused the spawning.
                ret_value = self._constraints.get(module, option)
            except ConstraintError:
                pass
            else:
                log.debug('mybuild: return %r', ret_value)
                return ret_value

            # Option without the module itself is meaningless. Fail-fast way
            # for case when the whole module has been previously excluded.
            self.constrain(module)

            ctx = self._build_ctx.context_for(module)
            vset = ctx.vset_for(option)

            vset.subscribe(self, partial(self._fork_and_spawn,
                self._constraints, module, option))
            # after that one shouldn't touch self._constraints anymore
            self._constraints.freeze()

            def constrain_all(values):
                constrain = self._constraints.constrain
                for value in values:
                    try:
                        yield constrain(module, option, value, fork=True)
                    except ConstraintError:
                        pass

            self._constraints = self._take_one_spawn_rest(constrain_all(vset))

            ret_value = self._constraints.get(module, option) # must not throw

            log.debug('mybuild: return %r', ret_value)
            return ret_value

    def _fork_and_spawn(self, constraints, module, option, value):
        log.debug('mybuild: fork %r with %r by %r.%s = %r',
            self._optuple, constraints, module, option, value)

        try:
            constraints = constraints.constrain(module, option, value,
                fork=True)
        except ConstraintError as e:
            log.debug('mybuild: fork error: %s', e)
            pass
        else:
            log.debug('mybuild: fork OK')
            self._spawn(constraints)

    def _take_one_spawn_rest(self, constraints_iterable):
        constraints_it = iter(constraints_iterable)

        try: # Retrieve the first one (if any) to return it.
            ret_constraints = constraints_it.next()
        except StopIteration:
            raise InstanceError('No viable choice to take')
        else:
            log.debug('mybuild: take %r', ret_constraints)

        # Spawn for the rest ones.
        self._spawn_all(constraints_it)

        return ret_constraints

    def _spawn_all(self, constraints_iterable):
        for constraints in constraints_iterable:
            self._spawn(constraints)

    def _spawn(self, constraints):
        log.debug('mybuild: spawn %r', constraints)
        self._post_new(self._build_ctx, self._optuple, constraints)

    def __repr__(self):
        return '<Instance %r with %r>' % (self._optuple, self._constraints)

    @classmethod
    def _new_type(cls, module_type, init_fxn):
        return type('Instance_M%s' % (module_type._module_name,),
                    (cls, module_type),
                    dict(__slots__=(), _init_fxn=init_fxn))


class Constraints(object):
    __slots__ = ('_dict',)

    class _ConstraintsDict(dict):
        """Delegates lookup for a missing key to the parent dictionary.

        Also overrides 'get' method extending it with an optional
        'insert_clone' argument.
        """
        __slots__ = ('_parent',)

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

        def merge_children(self, children, update_parent=True):
            """
            Caller must guarantee that each of 'children' is actually a child
            of this instance.
            """
            new_dict = type(self)(parent=self)

            for child in children:
                child.flatten(self, update_parent)
                for key, value in child.iteritems():
                    if key in new_dict:
                        new_dict[key].update(value)
                    else:
                        new_dict[key] = value.clone()

            return new_dict

        def flatten(self, until_parent=None, update_parent=True):
            for parent in self._iter_parents(until_parent):
                for key, value in parent.iteritems():
                    if key not in self:
                        self[key] = value.clone()

            if update_parent:
                self._parent = until_parent

        def _iter_parents(self, until_parent=None):
            parent = self._parent

            while parent is not until_parent:
                current = parent
                try:
                    parent = parent._parent
                except AttributeError:
                    assert parent is None
                    raise InternalError(
                        "'until_parent' must be a parent of this dict")

                yield current

        def __repr__(self):
            return dict.__repr__(self) if self._parent is None else \
                '%s <- %s' % (repr(self._parent), dict.__repr__(self))

    def __init__(self, _constraints_dict=None):
        super(Constraints, self).__init__()
        if _constraints_dict is None:
            _constraints_dict = self._ConstraintsDict()
        self._dict = _constraints_dict

    def freeze(self):
        self.__class__ = FrozenConstraints

    def fork(self):
        self.freeze()
        return Constraints(self._dict.fork())

    def merge_children(self, children, update_parent=True):
        log.debug('mybuild: parent=%r, merging %r', self, children)
        return Constraints(self._dict.merge_children(
                   imap(attrgetter('_dict'), children), update_parent))

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


class BuildContext(object):
    """docstring for BuildContext"""

    def __init__(self):
        super(BuildContext, self).__init__()
        self._modules = {}
        self._job_queue = deque()
        self._reent_locked = False

    def post(self, fxn):
        self._job_queue.append(fxn)

        with self.reent_lock():
            pass # to flush the queue

    @contextmanager
    def reent_lock(self):
        was_locked = self._reent_locked
        self._reent_locked = True

        try:
            yield
        finally:
            if not was_locked:
                self._job_queue_flush()
            self._reent_locked = was_locked

    def _job_queue_flush(self):
        queue = self._job_queue

        while queue:
            fxn = queue.popleft()
            fxn()

    def consider(self, optuple):
        self.context_for(optuple._module).consider(optuple)

    def register(self, instance):
        self.context_for(instance._module).register(instance)

    def context_for(self, module, option=None):
        try:
            context = self._modules[module]
        except KeyError:
            with self.reent_lock():
                context = self._modules[module] = ModuleContext(self,module)

        return context


class ModuleContext(object):
    """docstring for ModuleContext"""

    def __init__(self, build_ctx, module):
        super(ModuleContext, self).__init__()

        self.build_ctx = build_ctx
        self.module = module

        init_optuple = module._optuple_type._defaults
        self.vsets = init_optuple._make(OptionContext() for _ in init_optuple)

        self.instances = defaultdict(set) # { optuple : { instances... } }

        for a_tuple in izip_longest(*init_optuple, fillvalue=Ellipsis):
            self.consider(a_tuple)

    def consider(self, optuple):
        vsets_optuple = self.vsets

        what_to_extend = ((vset,v)
            for vset,v in izip(vsets_optuple, optuple)
            if v is not Ellipsis and v not in vset)

        for vset_to_extend, value in what_to_extend:
            log.debug('mybuild: extending %r with %r', vset_to_extend, value)
            vset_to_extend.add(value)

            sliced_vsets = (vset if vset is not vset_to_extend else (value,)
                for vset in vsets_optuple)

            for new_tuple in product(*sliced_vsets):
                self.module._instance_type._post_new(self.build_ctx,
                    vsets_optuple._make(new_tuple))

    def register(self, instance):
        self.instances[instance._optuple].add(instance)

    def vset_for(self, option):
        return getattr(self.vsets, option)


class OptionContext(MutableSet):
    """docstring for OptionContext"""

    def __init__(self):
        super(OptionContext, self).__init__()
        self._set = set()
        self._subscribers = []
        self._subscribers_keys = set() # XXX

    def add(self, value):
        if value in self:
            return
        self._set.add(value)

        subscribers = self._subscribers
        self._subscribers = None # our methods are not reenterable

        for s in subscribers:
            s(value)

        self._subscribers = subscribers

    def discard(self, value):
        if value not in self:
            return
        raise NotImplementedError

    def subscribe(self, key, fxn):
        assert key not in self._subscribers_keys
        self._subscribers_keys.add(key)
        self._subscribers.append(fxn)

    def __iter__(self):
        return iter(self._set)
    def __len__(self):
        return len(self._set)
    def __contains__(self, value):
        return value in self._set

    def __repr__(self):
        return '<OptionContext %r>' % (self._set,)


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


###############################################################################

log.zones = {'mybuild'}
log.verbose = True
log.init_log()

def check(module):
    wrapped = module._instance_type._init_fxn
    @wraps(wrapped)
    def wrapper(mod, *args, **kwargs):
        try:
            wrapped(mod, *args, **kwargs)
        except:
            # print_exc()
            raise
    module._instance_type._init_fxn = wrapper
    return module

@module
def conf(mod, z=None):
    mod._build_ctx.consider(m0(o=42))
    mod.constrain(m0(o=42))

@module
def m0(mod, o):
    mod1 = mod.ask(m1)
    t = "with m1" if mod1 else "no m1"
    log.debug("mybuild: <m0> o=%s, %s, m1.x=%r" % (o, t, mod1.x))

@module
def m1(mod, x=11):
    mod0 = mod.ask(m0)
    if mod0.o < 43:
        mod._build_ctx.consider(m0(o=mod0.o + 1))
    log.debug("myconstrain: <m1> x=%s, m0.o=%d" % (x, mod0.o))

if __name__ == '__main__':
    bctx = BuildContext()
    # bctx.consider(m0(o=42))
    # bctx.consider(m0(o=41))
    bctx.consider(conf())
    # for o in bctx._modules[m0].instances.keys():
    #     print o



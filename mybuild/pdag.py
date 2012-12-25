"""
Predicate Directed Acyclic Graph.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-29"

__all__ = [
    "Pdag",
    "PdagNode",
    "PdagContext",
    "PdagContextError",
    "DictBasedPdagContext",
    "AtomicNode",
    "ConstNode",
    "ConstraintNode",
    "Atom",
    "TrueAtomic",
    "FalseAtomic",
    "TrueConstraint",
    "FalseConstraint",
    "And",
    "Or",
    "Not",
    "Implies",
    "AtMostOneConstraint",
    "AllEqualConstraint",
]


import abc
from collections import namedtuple
from operator import attrgetter

import logs as log


class PdagContext(object):
    """
    Defines context protocol for interacting with Pdag nodes.
    """
    __metaclass__ = abc.ABCMeta
    __slots__ = ()

    @abc.abstractmethod
    def __getitem__(self, pnode):
        """
        Fetch the state of a given pnode in the current context.

        Raises:
            KeyError:
                When no value is associated with the node.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def __contains__(self, pnode):
        """
        Tells whether a given pnode has a value in the current context.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _check_and_set(self, pnode, value):
        """
        Set value of a given pnode.

        Returns:
            An old value (which is the same as new one), if any,
            or None otherwise.

        Raises:
            PdagContextError:
                When another value has already been set for this pnode.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _do_eval_unset(self, pnodes):
        raise NotImplementedError

    def get(self, pnode, default=None):
        """
        Retrieves the value of a given pnode, if any. Otherwise returns
        'default' (instead of raising KeyError).
        """
        try:
            return self[pnode]
        except KeyError:
            return default

    def check(self, pnode, value):
        """
        Check the value of a pnode against the given one.

        Args:
            pnode:
                The node, whichs value to test. If not set, its value is
                assumed to be None.
            value:
                True, False, or None.

        Returns:
            Whether the value of the pnode is the same as 'value'.
        """
        return self.get(pnode) is value

    def store(self, pnode, value, notify_on_set=True):
        """
        Set value of a given pnode.

        Depending on a 'notify_on_set' argument, setting a *new* value may
        result in calling 'context_setting' on the target pnode which may in
        turn set values for other nodes.

        Args:
            pnode:
                Obviously, the target pnode to set the value for.
            value (bool):
                The value for the target pnode, which must not conflict with an
                existing value, if any. Otherwise a PdagContextError is raised.
                In other words, operation succeeds iff
                    pnode not in ctx or ctx[pnode] == value
            notify_on_set (bool):
                Tells whether to call 'PdagNode.context_setting' or not.

        Returns:
            An old value (which is the same as new one), if any,
            or None otherwise.

        Raises:
            PdagContextError:
                When another value has already been set for this pnode.
        """

        old_value = self._check_and_set(pnode, value)

        if old_value is None and notify_on_set:
            pnode.context_setting(self, value)

        return old_value

    __setitem__ = store

    def store_all(self, pnodes, value, notify_on_set=True):
        """
        Batch version of 'store' which first stores a value for all nodes
        and only after that notifies newly set ones (if 'notify_on_set' is on).
        """

        if notify_on_set:
            pnodes_to_notify = [pnode
                for pnode in pnodes
                    if self._check_and_set(pnode, value) is None]

            for pnode in pnodes_to_notify:
                pnode.context_setting(self, value)

        else:
            for pnode in pnodes:
                self._check_and_set(pnode, value)

    def eval_unset(self, pnodes):
        """
        Requires given nodes to be evaluated.

        Args:
            pnodes:
                Iterable of nodes which must obtain values in order to satisfy
                the value of the first argument. Usually these are operands of
                'pnode'. May contain not only unset nodes.
        """
        self._do_eval_unset(self.ifilter_unset(pnodes))

    def ifilter_unset(self, pnodes):
        return (pnode for pnode in pnodes if self.get(pnode) is None)

    def iter_values_of(self, pnodes):
        return (self.get(pnode) for pnode in pnodes)

    def iter_pairs_of(self, pnodes):
        return ((pnode, self.get(pnode)) for pnode in pnodes)


class DictBasedPdagContext(PdagContext):
    """
    Context backed by a dictionary.
    """
    __slots__ = '_dict'

    def __init__(self, dict_):
        super(DictBasedPdagContext, self).__init__()
        self._dict = dict_

    def __getitem__(self, pnode):
        return self._dict[pnode]

    def __contains__(self, pnode):
        return pnode in self._dict

    def _check_and_set(self, pnode, value):
        assert isinstance(value, bool)

        self_dict = self._dict

        try:
            old_value = self_dict[pnode]

        except KeyError:
            self_dict[pnode] = value

        else:
            if old_value != value:
                assert isinstance(old_value, bool)
                raise PdagContextError

            return old_value


class PdagMeta(type):

    def __init__(cls, name, bases, attrs):
        super(PdagMeta, cls).__init__(name, bases, attrs)
        cls._registered_node_types = set()

    def node_type(cls, target):
        if not (isinstance(target, type) and
                issubclass(target, Pdag.NodeBase)):
            raise TypeError('Deco must be applied to a subclass '
                            'of Pdag.NodeBase, got %s object instead: %r' %
                            (type(target).__name__, target))

        if any(target in types
               for types in cls._iter_all_node_types_sets()):
            raise ValueError('%s type has been already registered in '
                             'class %s' % (target.__name__, cls.__name__))

        cls._registered_node_types.add(target)

        return target

    def _iter_all_node_types_sets(cls):
        for base in cls.__mro__:
            if isinstance(base, PdagMeta):
                yield base._registered_node_types

    def _iter_all_node_types(cls):
        for types in cls._iter_all_node_types_sets():
            for node_type in types:
                yield node_type


class Pdag(object):
    __metaclass__ = PdagMeta

    class NodeBase(object):

        class __metaclass__(type):
            def __new__(cls, name, bases, attrs):
                attrs.setdefault('__slots__', ())
                return type.__new__(cls, name, bases, attrs)

            def _extend_type_with(cls, *bases):
                return type(cls.__name__, (cls,) + bases, {})

        def __new__(cls, *args, **kwargs):
            try:
                cls._pdag
            except AttributeError:
                raise RuntimeError("Don't instantiate this class directly, "
                                   "use pdag.new(%s, ...) instead" %
                                   cls.__name__)
            else:
                return super(Pdag.NodeBase, cls).__new__(cls, *args, **kwargs)

        @classmethod
        def _new(cls, *args, **kwargs):
            canonical = cls._canonicalize_args(*args, **kwargs)

            cache = cls._pnode_map
            try:
                ret = cache[cls, canonical]
            except KeyError:
                ret = cache[cls, canonical] = cls(*args, **kwargs)

            return ret

        @classmethod
        def _canonicalize_args(cls, *args, **kwargs):
            """
            Implementation must return a canonical representation of given
            arguments.
            """
            return cls._starargs(*args, **kwargs)

        @classmethod
        def _starargs(cls, *args, **kwargs):
            return (args, frozenset(kwargs.iteritems()))

    nodes = property(lambda self: set(self._node_map.itervalues()))

    @property
    def atoms(self):
        return [node for node in self.nodes if isinstance(node, Atom)]

    def __init__(self):
        super(Pdag, self).__init__()

        self._node_map = {}

        class PdagType(object):
            __slots__ = ()

            _pdag = self
            _pnode_map = self._node_map

        node_types = self._node_types = {}
        for node_type in type(self)._iter_all_node_types():
            node_types[node_type] = node_type._extend_type_with(PdagType)

        # self._set_atoms(atoms)

    def __getitem__(self, node_type):
        try:
            return self._node_types[node_type]
        except KeyError:
            raise KeyError('Must register %s class using @%s.node_type' %
                           (node_type.__name__, type(self).__name__))

    def new(self, node_type, *args, **kwargs):
        return self[node_type]._new(*args, **kwargs)

    def new_const(self, const_value, operand=None):
        if operand is None:
            return self.new(ConstAtomicNode.atomic_types[const_value])
        else:
            return self.new(ConstConstraintNode.constraint_types[const_value],
                            operand)


class PdagNode(Pdag.NodeBase):
    """docstring for PdagNode"""

    __slots__ = '_outgoing'

    costs = (0, 0) # cost = pnode.costs[value] # value is either True or False

    def __init__(self):
        self._outgoing = set()

    def _new_incoming(self, incoming):
        incoming._outgoing.add(self)
        return incoming

    def _incoming_setting(self, incoming, ctx, value):
        """Here 'value' is either True or False."""
        raise NotImplementedError

    def _notify_outgoing(self, ctx, value):
        log.debug("pdag: outgoing: [%s]",
                  ', '.join(str(out.bind(ctx)) for out in self._outgoing))
        for out in self._outgoing:
            out._incoming_setting(self, ctx, value)

    def _store_self(self, ctx, value):
        if ctx.store(self, value, notify_on_set=False) is None:
            self._notify_outgoing(ctx, value)

    def context_setting(self, ctx, value):
        self._notify_outgoing(ctx, value)

    def bind(self, ctx):
        return PnodeInContext(self, ctx)


class ConstraintNode(PdagNode):
    """
    Marker class for a node that may constrain values of incoming nodes
    even without having its own value specified.
    """


class AtomicNode(PdagNode):
    """Marker class for leaf nodes."""


@Pdag.node_type
class Atom(AtomicNode):
    """To be extended by the client."""
    costs = (0, 1)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):
            super(Atom, self).context_setting(ctx, value)


class ConstNode(PdagNode):
    """Constrains a node to take a constant value."""

    const_value = None # overridden by subclasses

    def _incoming_setting(self, incoming, ctx, value):
        if value is not self.const_value:
            raise PdagContextError
        self._store_self(ctx, value)

    def context_setting(self, ctx, value):
        if value is not self.const_value:
            raise PdagContextError
        self._notify_outgoing(ctx, value)

    def __repr__(self):
        return repr(self.const_value).upper()

# Markers to simplify isinstance checks.
class TrueConstNode(ConstNode):  const_value = True
class FalseConstNode(ConstNode): const_value = False

class ConstAtomicNode(ConstNode, AtomicNode):
    atomic_types = (None, None)  # overwritten below

    def negate(self):
        return self._pdag.new_const(not self.value)

    @classmethod
    def _canonicalize_args(self):
        pass

@Pdag.node_type
class TrueAtomic(TrueConstNode, ConstAtomicNode): pass
@Pdag.node_type
class FalseAtomic(FalseConstNode, ConstAtomicNode): pass

ConstAtomicNode.atomic_types = (FalseAtomic, TrueAtomic)


class SingleOperandNode(PdagNode):
    """A node with a single operand."""
    __slots__ = '_operand'

    def __init__(self, operand):
        super(SingleOperandNode, self).__init__()
        self._operand = operand
        self._new_incoming(operand)

    @classmethod
    def _canonicalize_args(cls, operand):
        return operand


class ConstConstraintNode(SingleOperandNode, ConstNode, ConstraintNode):
    constraint_types = (None, None)  # overwritten below

    @classmethod
    def _new(cls, operand):
        if isinstance(operand, ConstNode):
            if operand.const_value is cls.const_value:
                return operand
            # else maybe die here
        elif isinstance(operand, Not):
            return cls._pdag.new_const(not cls.const_value, operand._operand)
        else:
            return super(ConstConstraintNode, cls)._new(operand)

    def context_setting(self, ctx, value):
        ctx[self._operand] = value
        super(ConstConstraintNode, self).context_setting(ctx, value)

@Pdag.node_type
class TrueConstraint(TrueConstNode, ConstConstraintNode): pass
@Pdag.node_type
class FalseConstraint(FalseConstNode, ConstConstraintNode): pass

ConstConstraintNode.constraint_types = (FalseConstraint, TrueConstraint)


class OperandSetNode(PdagNode):
    """A node which may have an arbitrary number of equivalent operands."""
    __slots__ = '_operands'

    class OperandError(Exception):
        pass

    def __init__(self, *operands):
        super(OperandSetNode, self).__init__()

        self._operands = set()
        for operand in operands:
            self._new_operand(operand)

    @classmethod
    def _canonicalize_args(cls, *operands):
        return frozenset(operands)

    def _new_operand(self, operand):
        """Generally subclasses should use this instead of '_new_incoming'."""
        self._operands.add(operand)
        return self._new_incoming(operand)

    def _single_unset_operand(self, ctx, break_on=None):
        """
        Returns:
            Single operand left unset (if any), None if all operands are set.
        Raises:
            self.OperandError:
                If more than one operands are still unset (in this case also
                'eval_unset' method of context is called), or when 'break_on'
                is not None and an operand with that value is encountered.
        """
        found_single = None

        for operand, value in ctx.iter_pairs_of(self._operands):

            if value is None:
                if found_single is not None:
                    if self in ctx:
                        ctx.eval_unset(self._operands)
                    break

                found_single = operand

            elif value is break_on:
                break

        else:
            return found_single

        raise self.OperandError

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__,
                           ', '.join(map(repr, self._operands)))


class LatticeOpNode(OperandSetNode):
    """
    An operation with the following properties:
      - Associative: op(op(A, B), C) == op(A, op(B, C))
      - Commutative: op(A, B) == op(B, A)
      - Idempotent: op(A, A) == op(A) == A

    Special elements:
      - Identity: op(Identity, A) == A; op() == Identity
      - Zero: op(Zero, A) == Zero

    """

    @classmethod
    def _new(cls, *operands):
        new_operands = set()

        for operand in operands:
            if isinstance(operand, ConstNode):
                if operand.const_value is cls.zero:
                    return operand
            else:
                new_operands.add(operand)

        if not new_operands:
            return cls._pdag.new_const(cls.identity)
        elif len(new_operands) == 1:
            operand, = new_operands
            return operand
        else:
            return super(LatticeOpNode, cls)._new(*new_operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value is self.zero:
                log.debug("pdag: operand value is zero")
                self._store_self(ctx, value)

            elif not ctx.check(self, self.identity):  # zero or None
                log.debug("pdag: operand value is identity")
                self._eval_operands(ctx)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if value is self.identity:
                log.debug("pdag: new value is identity")
                ctx.store_all(self._operands, value)
                # for operand in self._operands:
                #     ctx[operand] = value

            else:
                log.debug("pdag: new value is zero")
                self._eval_operands(ctx)

            self._notify_outgoing(ctx, value)

    def _eval_operands(self, ctx):
        with log.debug("pdag: %s: %s, evaluating: [%s]",
                       type(self).__name__, self.bind(ctx),
                       ', '.join(str(i.bind(ctx)) for i in self._operands)):

            zero = self.zero
            try:
                last_unset = self._single_unset_operand(ctx, break_on=zero)

            except self.OperandError:
                log.debug("pdag: too many unset operands, or zero encountered")

            else:
                if last_unset is None:
                    log.debug("pdag: all operands are identity")
                    self._store_self(ctx, self.identity)

                elif ctx.check(self, zero):
                    log.debug("pdag: last unset operand: %s", last_unset)
                    ctx[last_unset] = zero

    def __repr__(self):
        return self._repr_sign.join(map(repr, self._operands)).join('()')

@Pdag.node_type
class And(LatticeOpNode):

    identity = True
    zero     = False

    _repr_sign = ' & '

@Pdag.node_type
class Or(LatticeOpNode):

    identity = False
    zero     = True

    _repr_sign = ' | '


@Pdag.node_type
class Not(SingleOperandNode):
    """
    Logical negation.

       op    self
    -----   -----
     True   False
    False    True
    """

    @classmethod
    def _new(cls, operand):
        if isinstance(operand, Not):
            return operand._operand
        elif isinstance(operand, ConstNode):
            return cls._pdag.new_const(not operand.const_value)
        else:
            return super(Not, cls)._new(operand)

    def _incoming_setting(self, incoming, ctx, value):
        assert incoming is self._operand

        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            self._store_self(ctx, not value)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            ctx[self._operand] = not value
            self._notify_outgoing(ctx, value)

    def __repr__(self):
        return '(~%r)' % self._operand


@Pdag.node_type
class Implies(PdagNode):
    """
    Simple logical implication.

       if    then    self
    -----   -----   -----
     True    True    True
     True   False   False
    False    True    True
    False   False    True
    """
    __slots__ = '_if', '_then'

    def __init__(self, if_, then):
        super(Implies, self).__init__()

        self._if = if_
        self._new_incoming(if_)

        self._then = then
        self._new_incoming(then)

    @classmethod
    def _new(cls, if_, then):
        if (isinstance(if_, FalseConstNode) or
              isinstance(then, TrueConstNode)):
            return cls._pdag.new_const(True)

        elif isinstance(if_, TrueConstNode):
            return then

        elif isinstance(then, FalseConstNode):
            return cls._pdag.new(Not, if_)

        else:
            return super(Implies, cls)._new(if_, then)

    @classmethod
    def _canonicalize_args(cls, if_, then):
        return if_, then

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            incoming_is_then = incoming is self._then
            other_operand = self._if if incoming_is_then else self._then

            if incoming_is_then is value:
                self._store_self(ctx, True)
                ctx.eval_unset((other_operand,))

            else:
                self_value = ctx.get(self)
                if self_value is not None:
                    ctx[other_operand] = self_value ^ incoming_is_then

                else:
                    other_value = ctx.get(other_operand)
                    if other_value is not None:
                        self._store_self(ctx, other_value ^ incoming_is_then)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if not value:
                ctx[self._if] = True
                ctx[self._then] = False

            elif ctx.check(self._if, True):
                ctx[self._then] = True

            elif ctx.check(self._then, False):
                ctx[self._if] = False

            else:
                ctx.eval_unset((self._if, self._then))

            self._notify_outgoing(ctx, value)

    def __repr__(self):
        return '(%r => %r)' % (self._if, self._then)


@Pdag.node_type
class AtMostOneConstraint(OperandSetNode, ConstraintNode):
    """
    Allows at most a single operand to be True. Evaluates to True if a single
    operand is True, and to False if *all* operands are also False.

      op1     ...     opN    self
    -----   -----   -----   -----
     True   False   False    True
    False   False   False    False

    When there is no operands evaluates to False.
    """

    @classmethod
    def _new(cls, *operands):
        operands = set(operands)

        if not operands:
            return cls._pdag.new_const(False)
        elif len(operands) == 1:
            operand, = operands
            return operand
        else:
            return super(AtMostOneConstraint, cls)._new(*operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value:
                ctx.store_all((operand for operand in self._operands
                               if operand is not incoming), False)

                self._store_self(ctx, True)

            else:
                self._eval_operands(ctx)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if not value:
                ctx.store_all(self._operands, False)

            else:
                self._eval_operands(ctx)

            self._notify_outgoing(ctx, value)

    def _eval_operands(self, ctx):
        with log.debug("pdag: %s: %s, evaluating: [%s]",
                       type(self).__name__, self.bind(ctx),
                       ', '.join(str(i.bind(ctx)) for i in self._operands)):
            try:
                last_unset = self._single_unset_operand(ctx, break_on=True)

            except self.OperandError:
                log.debug("pdag: too many unset operands, or True encountered")

            else:
                if last_unset is None:
                    log.debug("pdag: all operands are set to False")
                    self._store_self(ctx, False)

                else:
                    log.debug("pdag: last unset operand: %s", last_unset)
                    self_value = ctx.get(self)
                    if self_value is not None:
                        ctx[last_unset] = self_value


@Pdag.node_type
class AllEqualConstraint(OperandSetNode, ConstraintNode):
    """
    Forces all operands to take the same value, and evaluates to that value.
    May be considered as a common alias for its operands.

      op1     ...     opN    self
    -----   -----   -----   -----
     True    True    True    True
    False   False   False    False
    """

    @classmethod
    def _new(cls, *operands):
        operands = set(operands)

        if len(operands) == 1:
            operand, = operands
            return operand
        else:
            return super(AllEqualConstraint, cls)._new(*operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            ctx.store_all(self._operands, value)
            self._store_self(ctx, value)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            ctx.store_all(self._operands, value)
            self._notify_outgoing(ctx, value)


class PnodeInContext(namedtuple('_PnodeInContext', 'node context')):
    __slots__ = ()
    def __repr__(self):
        node = self.node
        try:
            value = self.context[node]
        except KeyError:
            return repr(node)
        else:
            return '%r=%r' % (node, value)


class PdagContextError(ValueError):
    """Raised by PdagContext on an attempt to set an inappropriate value."""


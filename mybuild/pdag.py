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
    "And",
    "Or",
    "Not",
    "Implies",
    "AtMostOneConstraint",
    "AllEqualConstraint",
    "Atom",
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

    @abc.abstractproperty
    def _dict(self):
        """
        Implementation must provide a dictionary-like object which is used as
        an internal storage of the context.
        """
        raise NotImplementedError

    def __getitem__(self, pnode):
        """
        Fetch the state of a given pnode in the current context.

        Returns:
            Tristate (None, True or False) indicating the current value of the
            specified pnode.

        Never raises KeyError.
        """
        try:
            return self._dict[pnode]
        except KeyError:
            return None

    def __setitem__(self, pnode, value):
        """
        An alias for 'store' method with 'notify_pnode=True'.
        """
        self.store(pnode, value)

    def store(self, pnode, value, notify_pnode=True):
        """
        Set value of a given pnode.

        Depending on a 'notify_pnode' argument, setting a *new* value may
        result in calling 'context_setting' on the target pnode which may in
        turn set values for other nodes.

        Args:
            pnode:
                Obviously, the target pnode to set the value for.
            value (bool):
                The value for the target pnode, which must not conflict with an
                existing value, if any. Otherwise a PdagContextError is raised.
                In other words, operation succeeds iff
                    ctx[pnode] is None or ctx[pnode] == value
            notify_pnode (bool):
                Tells whether to call 'PdagNode.context_setting' or not.

        Returns:
            An old value (which is the same as new one), if any,
            or None otherwise.

        Raises:
            PdagContextError:
                When another value has already been set for this pnode.
        """
        assert isinstance(value, bool)

        self_dict = self._dict

        try:
            old_value = self_dict[pnode]

        except KeyError:
            self_dict[pnode] = value

            if notify_pnode:
                pnode.context_setting(self, value)

        else:
            if old_value != value:
                raise PdagContextError

            return old_value

    def store_all(self, pnodes, value, notify_pnode=True):
        if notify_pnode:
            pnodes_to_notify = []
            for pnode in pnodes:
                if self.store(pnode, value, notify_pnode=False) is None:
                    pnodes_to_notify.append(pnode)

            for pnode in pnodes_to_notify:
                pnode.context_setting(self, value)

        else:
            for pnode in pnodes:
                self.store(pnode, value, notify_pnode=False)


class Pdag(object):

    atoms = property(attrgetter('_atoms'))
    nodes = property(attrgetter('_nodes'))

    def __init__(self, *atoms):
        super(Pdag, self).__init__()
        self._set_atoms(atoms)

    def _set_atoms(self, atoms):
        self._atoms = atoms = frozenset(atoms)
        for atom in atoms:
            if not isinstance(atom, AtomicNode):
                raise TypeError(
                    "Atomic node expected, got '%s' object instead" %
                    type(atom).__name__)
        self._nodes = frozenset(self._hull_set(atoms))

    @classmethod
    def _hull_set(cls, nodes):
        unvisited = set(nodes)
        visited = set()

        while unvisited:
            node = unvisited.pop()

            outgoing = node._outgoing = frozenset(node._outgoing)
            visited.add(node)

            unvisited |= outgoing
            unvisited -= visited

        return visited


class PdagNode(object):
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
        if ctx.store(self, value, notify_pnode=False) is None:
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
    __slots__ = ()


class AtomicNode(PdagNode):
    """Marker class for leaf nodes."""
    __slots__ = ()


class Atom(AtomicNode):
    """To be extended by the client."""
    __slots__ = ()
    costs = (0, 1)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):
            super(Atom, self).context_setting(ctx, value)


class ConstNode(AtomicNode):
    """Constrains a node to take a constant value."""
    __slots__ = ()

    const_value = None       # overridden by subclasses
    instances = (None, None) # overwritten below

    def context_setting(self, ctx, value):
        if value is not self.const_value:
            ctx.store(self, not value) # Let it fall.
        self._notify_outgoing(ctx, value)

class True_(ConstNode):
    __slots__ = ()
    const_value = True

class False_(ConstNode):
    __slots__ = ()
    const_value = False

ConstNode.instances = (False_, True_)


class OperandSetNode(PdagNode):
    __slots__ = '_operands'

    class OperandError(Exception):
        pass

    def __init__(self, operands):
        super(OperandSetNode, self).__init__()

        self._operands = set()
        for operand in operands:
            self._new_operand(operand)

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
                If more than one operands are still unset, or when 'break_on'
                is not None and an operand with that value is encountered.
        """
        found_single = None

        for operand in self._operands:
            operand_value = ctx[operand]

            if operand_value is None:
                if found_single is not None:
                    break

                found_single = operand

            elif operand_value is break_on:
                break

        else:
            return found_single

        raise self.OperandError

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__,
                           ', '.join(map(repr, self._operands)))


class LatticeOpNode(OperandSetNode):
    """Associative, commutative and idempotent operation."""
    __slots__ = ()

    def __init__(self, *operands):
        super(LatticeOpNode, self).__init__(operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value is self._zero:
                log.debug("pdag: operand value is zero")
                self._store_self(ctx, value)

            elif ctx[self] is not self._identity:
                log.debug("pdag: operand value is identity")
                self._eval_operands(ctx)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if value is self._identity:
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

            zero = self._zero
            try:
                last_unset = self._single_unset_operand(ctx, break_on=zero)

            except self.OperandError:
                log.debug("pdag: too many unset operands, or zero encountered")

            else:
                if last_unset is None:
                    log.debug("pdag: all operands are identity")
                    self._store_self(ctx, self._identity)

                elif ctx[self] is zero:
                    log.debug("pdag: last unset operand: %s", last_unset)
                    ctx[last_unset] = zero

    def __repr__(self):
        return self._repr_sign.join(map(repr, self._operands)).join('()')

class And(LatticeOpNode):
    __slots__ = ()

    _identity = True
    _zero     = False

    _repr_sign = ' & '

class Or(LatticeOpNode):
    __slots__ = ()

    _identity = False
    _zero     = True

    _repr_sign = ' | '


class Not(PdagNode):
    """
    Logical negation.

       op    self
    -----   -----
     True   False
    False    True
    """
    __slots__ = '_operand'

    def __init__(self, operand):
        super(Not, self).__init__()
        self._operand = operand
        self._new_incoming(operand)

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

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if (incoming is self._then) is value:
                self._store_self(ctx, True)

            else:
                other_operand = self._then if value else self._if

                self_value = ctx[self]
                if self_value is not None:
                    ctx[other_operand] = self_value ^ (not value)

                else:
                    other_value = ctx[other_operand]
                    if other_value is not None:
                        self._store_self(ctx, other_value ^ (not value))

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if not value:
                ctx[self._if] = True
                ctx[self._then] = False

            elif ctx[self._if] is True:
                ctx[self._then] = True

            elif ctx[self._then] is False:
                ctx[self._if] = False

            self._notify_outgoing(ctx, value)

    def __repr__(self):
        return '(%r => %r)' % (self._if, self._then)


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
    __slots__ = ()

    def __init__(self, *operands):
        super(AtMostOneConstraint, self).__init__(operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value:
                self._store_self(ctx, True)

                for operand in self._operands:
                    if operand is not incoming:
                        ctx[operand] = False

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
                    self_value = ctx[self]
                    if self_value is not None:
                        ctx[last_unset] = self_value


class AllEqualConstraint(OperandSetNode, ConstraintNode):
    """
    Forces all operands to take the same value, and evaluates to that value.
    May be considered as a common alias for its operands.

      op1     ...     opN    self
    -----   -----   -----   -----
     True    True    True    True
    False   False   False    False
    """
    __slots__ = ()

    def __init__(self, *operands):
        super(AllEqualConstraint, self).__init__(operands)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            self._store_self(ctx, value)

            for operand in self._operands:
                if operand is not incoming:
                    ctx[operand] = value

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            for operand in self._operands:
                ctx[operand] = value

            self._notify_outgoing(ctx, value)


class PnodeInContext(namedtuple('_PnodeInContext', 'node context')):
    __slots__ = ()
    def __repr__(self):
        node = self.node
        value = self.context[node]
        return '%r=%r' % (node, value) if value is not None else repr(node)


class PdagContextError(ValueError):
    """Raised by PdagContext on an attempt to set an inappropriate value."""


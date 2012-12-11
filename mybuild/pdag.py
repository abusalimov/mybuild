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
        Calls 'store' method with 'notify_pnode=True'.
        """
        self.store(pnode, value, notify_pnode=True)

    def store(self, pnode, value, notify_pnode=False):
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


class Pdag(object):

    atoms = property(attrgetter('_atoms'))
    nodes = property(attrgetter('_nodes'))

    def __init__(self, *atoms):
        self._atoms = atoms = frozenset(atoms)
        for atom in atoms:
            if not isinstance(atom, Atom):
                raise TypeError
        self._nodes = frozenset(self._hull(atoms))

    @classmethod
    def _hull(cls, nodes):
        unvisited = set(nodes)
        visited = set()

        while unvisited:
            node = unvisited.pop()
            visited.add(node)
            outgoing = node._outgoing = frozenset(node._outgoing)
            unvisited |= node._outgoing - visited

        return visited


class PdagNode(object):
    """docstring for PdagNode"""
    __slots__ = '_outgoing'

    costs = (0, 1) # cost = pnode.costs[value] # value is either True or False

    def __init__(self):
        self._outgoing = set()

    def _new_incoming(self, incoming):
        incoming._outgoing.add(self)

    def _incoming_setting(self, incoming, ctx, value):
        """Here 'value' is either True or False."""
        raise NotImplementedError

    def context_setting(self, ctx, value):
        log.debug("pdag: outgoing: [%s]",
                  ', '.join(str(out.bind(ctx)) for out in self._outgoing))
        for out in self._outgoing:
            out._incoming_setting(self, ctx, value)

    def bind(self, ctx):
        return PnodeInContext(self, ctx)


class LatticeOp(PdagNode):
    """Associative, commutative and idempotent operation."""
    __slots__ = '_incoming'

    def __init__(self, *incoming):
        super(LatticeOp, self).__init__()
        self._incoming = set()
        for operand in incoming:
            self._new_incoming(operand)

    def _new_incoming(self, incoming):
        self._incoming.add(incoming)
        super(LatticeOp, self)._new_incoming(incoming)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value is self._zero:
                log.debug("pdag: operand value is zero")
                ctx.store(self, value)

            else:
                log.debug("pdag: operand value is identity")
                self._eval_operands(ctx)

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if value is self._identity:
                log.debug("pdag: new value is identity")
                for operand in self._incoming:
                    ctx[operand] = value

            else:
                log.debug("pdag: new value is zero")
                self._eval_operands(ctx)

            super(LatticeOp, self).context_setting(ctx, value)

    def _eval_operands(self, ctx):
        with log.debug("pdag: %s: %s, evaluating: [%s]",
                       type(self).__name__, self.bind(ctx),
                       ', '.join(str(i.bind(ctx)) for i in self._incoming)):

            zero = self._zero

            last_unset_operand = None
            for operand in self._incoming:
                value = ctx[operand]

                if value is zero:
                    log.debug("pdag: operand value is zero")
                    ctx.store(self, zero)
                    return

                if value is None:
                    if last_unset_operand is not None:
                        log.debug("pdag: too many unset operands")
                        return
                    last_unset_operand = operand

            if last_unset_operand is None:
                log.debug("pdag: all operands are identity")
                ctx.store(self, self._identity)

            elif ctx[self] is zero:
                log.debug("pdag: sole unset operand left: %s",
                          last_unset_operand)
                ctx[last_unset_operand] = zero

            else:
                log.debug("pdag: sole operand left, but self value is not zero")

    # def __repr__(self):
    #     return self._repr_sign.join(map(repr, self._incoming)).join('()')
    def __str__(self):
        return self._repr_sign.join(map(str, self._incoming)).join('()')

class And(LatticeOp):
    _identity = True
    _zero     = False

    _repr_sign = '&'

class Or(LatticeOp):
    _identity = False
    _zero     = True

    _repr_sign = '|'


class Not(PdagNode):
    __slots__ = '_operand'

    def __init__(self, operand=None):
        super(Not, self).__init__()
        self._operand = None
        if operand is not None:
            self._new_incoming(operand)

    def _new_incoming(self, incoming):
        assert self._operand is None
        self._operand = incoming
        super(Not, self)._new_incoming(incoming)

    def _incoming_setting(self, incoming, ctx, value):
        assert incoming is self._operand

        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            ctx[self] = not value

    def context_setting(self, ctx, value):
        assert self._operand is not None

        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            ctx[self._operand] = not value
            super(Not, self).context_setting(ctx, value)

    # def __repr__(self):
    #     return '~%r' % self._operand
    def __str__(self):
        return '~%s' % self._operand


class Atom(PdagNode):
    """To be extended by the client."""
    __slots__ = ()

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):
            super(Atom, self).context_setting(ctx, value)


class PnodeInContext(namedtuple('_PnodeInContext', 'node context')):
    def __str__(self):
        node = self.node
        value = self.context[node]
        return '%s=%s' % (node, value) if value is not None else str(node)


class PdagContextError(ValueError):
    """Raised by PdagContext on an attempt to set an inappropriate value."""


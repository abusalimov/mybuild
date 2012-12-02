"""
Predicate Directed Acyclic Graph.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-29"

__all__ = [
    "Pdag",
    "PdagNode",
    "And",
    "Or",
    "Not",
    "Atom",
]


from collections import namedtuple
from operator import attrgetter

import logs as log


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

    def __init__(self):
        self._outgoing = set()

    def new_incoming(self, incoming):
        incoming._outgoing.add(self)

    def _incoming_setting(self, incoming, ctx, value):
        """Here 'value' is either True, False, or None (for deleting)."""
        raise NotImplementedError

    def context_setting(self, ctx, value):
        log.debug("pdag: outgoing: [%s]",
                  ', '.join(str(o.bind(ctx)) for o in self._outgoing))
        for out in self._outgoing:
            out._incoming_setting(self, ctx, value)

    def bind(self, ctx):
        return NodeInContext(self, ctx)


class LatticeOp(PdagNode):
    """Associative, commutative and idempotent operation."""
    __slots__ = '_incoming'

    def __init__(self, *incoming):
        super(LatticeOp, self).__init__()
        self._incoming = set()
        for operand in incoming:
            self.new_incoming(operand)

    def new_incoming(self, incoming):
        self._incoming.add(incoming)
        super(LatticeOp, self).new_incoming(incoming)

    def _incoming_setting(self, incoming, ctx, value):
        with log.debug("pdag: %s: %s, operand %s", type(self).__name__,
                       self.bind(ctx), incoming.bind(ctx)):

            if value is self._identity:
                log.debug("pdag: value is identity")
                self._eval_operands(ctx)

            else:
                log.debug("pdag: value is zero")
                ctx[self] = value

    def context_setting(self, ctx, value):
        with log.debug("pdag: %s: %s", type(self).__name__, self.bind(ctx)):

            if value is self._identity:
                log.debug("pdag: value is identity")
                for operand in self._incoming:
                    ctx[operand] = value

            else:
                log.debug("pdag: value is zero")
                self._eval_operands(ctx)

            super(LatticeOp, self).context_setting(ctx, value)

    def _eval_operands(self, ctx):
        log.debug("pdag: evaluating operands: [%s]",
                  ', '.join(str(i.bind(ctx)) for i in self._incoming))

        identity = self._identity
        zero = not identity

        last_operand = None
        for operand in self._incoming:
            value = ctx[operand]

            if value is zero:
                log.debug("pdag: operand value is zero")
                ctx[self] = value
                return

            if value is None:
                if last_operand is not None:
                    log.debug("pdag: too many unset operands")
                    return
                last_operand = operand

        if last_operand is None:
            log.debug("pdag: all operands are identity")
            ctx[self] = identity

        elif ctx[self] is zero:
            log.debug("pdag: sole unset operand left: %s", last_operand)
            ctx[last_operand] = zero

        else:
            log.debug("pdag: sole operand left, but self value is not zero")

    # def __repr__(self):
    #     return self._repr_sign.join(map(repr, self._incoming)).join('()')
    def __str__(self):
        return self._repr_sign.join(map(str, self._incoming)).join('()')

class And(LatticeOp):
    _identity = True
    _repr_sign = '&'

class Or(LatticeOp):
    _identity = False
    _repr_sign = '|'


class Not(PdagNode):
    __slots__ = '_operand'

    def __init__(self, operand=None):
        super(Not, self).__init__()
        self._operand = None
        if operand is not None:
            self.new_incoming(operand)

    def new_incoming(self, incoming):
        assert self._operand is None
        self._operand = incoming
        super(Not, self).new_incoming(incoming)

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


class NodeInContext(namedtuple('_NodeInContext', 'node context')):
    def __str__(self):
        node = self.node
        value = self.context[node]
        return '%s=%s' % (node, value) if value is not None else str(node)


"""
The Graph of Predicates.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-29"

__all__ = [
    "Pgraph",
    "Node",
    "Literal",
    "Neglast",
    "Reason",

    "to_lset",
    "to_nvdict",

    "AtomicNode",
    "Atom",

    "ConstNode",
    "TrueConst",
    "FalseConst",

    "And",
    "Or",

    "Not",
    "Implies",

    "AtMostOne",
    "AllEqual",
]


from collections import Mapping
from collections import namedtuple

from compat import *

from util import bools
from util import Pair

import logs as log


class PgraphMeta(type):

    def __init__(cls, name, bases, attrs):
        super(PgraphMeta, cls).__init__(name, bases, attrs)
        cls._registered_node_types = set()

    def node_type(cls, target):
        if not (isinstance(target, type) and
                issubclass(target, Pgraph.NodeBase)):
            raise TypeError('Deco must be applied to a subclass '
                            'of Pgraph.NodeBase, got %s object instead: %r' %
                            (type(target).__name__, target))

        if any(target in types
               for types in cls._iter_all_node_types_sets()):
            raise ValueError('%s type has been already registered in '
                             'class %s' % (target.__name__, cls.__name__))

        cls._registered_node_types.add(target)

        return target

    def _iter_all_node_types_sets(cls):
        for base in cls.__mro__:
            if isinstance(base, PgraphMeta):
                yield base._registered_node_types

    def _iter_all_node_types(cls):
        for types in cls._iter_all_node_types_sets():
            for node_type in types:
                yield node_type


class Pgraph(object):
    """docstring for Pgraph"""
    __metaclass__ = PgraphMeta

    class NodeBase(object):
        __slots__ = ()

        def __new__(cls, *args, **kwargs):
            try:
                cls._pgraph
            except AttributeError:
                raise RuntimeError("Don't instantiate this class directly, "
                                   "use pgraph.new_node(%s, ...) instead" %
                                   cls.__name__)
            else:
                return super(Pgraph.NodeBase, cls).__new__(cls, *args, **kwargs)

        @classmethod
        def _new(cls, *args, **kwargs):
            cache = cls._pgraph._node_map
            cache_key = cls, cls._canonical_args(*args, **kwargs)

            try:
                ret = cache[cache_key]
            except KeyError:
                ret = cache[cache_key] = cls(*args, **kwargs)

            return ret

        @classmethod
        def _canonical_args(cls, *args, **kwargs):
            """
            Implementation must return a canonical representation of given
            arguments.
            """
            return cls._starargs(*args, **kwargs)

        @classmethod
        def _starargs(cls, *args, **kwargs):
            return (args, frozenset(iteritems(kwargs)))

    nodes = property(lambda self: set(itervalues(self._node_map)))

    @property
    def atoms(self):
        return [node for node in self.nodes if isinstance(node, Atom)]

    def __init__(self):
        super(Pgraph, self).__init__()

        node_types = self._node_types = {}
        for node_type in type(self)._iter_all_node_types():
            node_types[node_type] = type(node_type.__name__, (node_type,),
                                         dict(_pgraph=self))

        self._node_map = {}

    def new_node(self, node_type, *args, **kwargs):
        """
        Returns a node of the given type.

        All nodes are cached and subsequent calls with the same arguments will
        return the same object.
        """
        try:
            node_type = self._node_types[node_type]

        except KeyError:
            raise KeyError('Must register %s class using @%s.node_type' %
                           (node_type.__name__, type(self).__name__))

        else:
            return node_type._new(*args, **kwargs)

    def new_const(self, const_value, node=None, why=None):
        """
        Constrains a given node (if any) to the specified const_value.
        In case if node is None, returns a special constant node.
        """
        const_node = self.new_node(ConstNode.types[const_value])

        if node is not None:
            node[const_value].becauseof(const_node[const_value], why)
        else:
            node = const_node

        return node


class Node(Pgraph.NodeBase, Pair):
    """
    Each node is effectively a pair of two literals:
    one for False, and one for True. See Literal class below.
    """
    __slots__ = ()

    _costs = (0, 0)

    def __new__(cls, *args, **kwargs):
        new_node = super(Node, cls).__new__(cls,
                                            false=Literal(), true=Literal())

        for literal in new_node:
            literal.node = new_node

        for bool_value in bools:
            assert new_node[bool_value].value == bool_value

        return new_node

    def __init__(self, costs=None):
        super(Node, self).__init__()

        if costs is None:
            costs = self._costs

        for literal, literal_cost in zip(self, Pair._make(costs)):
            literal.cost = literal_cost


class Literal(object):
    """
    Depending on a node value the node may behave differently.
    Literal object describes such behavior.

    Literal object is tightly related to its node. Do not construct it manually.
    """
    __slots__ = 'node', 'cost', 'implies', 'imply_reasons', 'neglasts'

    value = property(lambda self: self is self.node[True])

    def __init__(self):
        super(Literal, self).__init__()

        self.implies = set()         # set of implied literals
        self.imply_reasons = list()  # precreated reason objects
        self.neglasts = dict()       # neglast-to-index_in_its_list mapping

    def __invert__(self):
        """Returns the opposite literal."""
        return self.node[not self.value]

    def __iter__(self):
        """Support for tuple unpacking: (node, value)"""
        return iter((self.node, self.value))

    @staticmethod
    def __imply(if_, then, why=None):
        if_.implies.add(then)
        if_.imply_reasons.append(Reason(why, then, if_))

    def therefore(self, other, why=None):
        """Implication: self => other"""

        if self is other:
            return

        if self is ~other:
            raise ValueError('Implication of self negation')

        if self.node._pgraph is not other.node._pgraph:
            raise ValueError('Must belong to the same Pgraph')

        self.__imply( self,   other,  why)
        self.__imply(~other, ~self,   why)

    def becauseof(self, other, why=None):
        """Implication: other => self"""
        other.therefore(self, why)

    def equivalent(self, other, why_therefore=None, why_becauseof=None):
        """Equivalence relation: other <=> self"""

        self.therefore(other, why_therefore)
        self.becauseof(other, why_becauseof)

    def therefore_all(self, others, why=None):
        """Group implication: self => all(others)"""

        for literal in to_lset(others):
            self.therefore(literal, why)

    def becauseof_all(self, others, why=None):
        """Group implication: all(others) => self"""

        node_values = to_nvdict(others)
        if node_values.pop(self.node, self.value) is not self.value:
            raise ValueError('Implication of self negation')

        if not node_values:
            self.node._pgraph.new_const(self.value, self.node, why)

        elif len(node_values) == 1:
            node, value = node_values.popitem()
            self.becauseof(node[value], why)

        else:
            neglast = Neglast(~self, node_values, why)

            for index, literal in enumerate(neglast.literals):
                if self.node._pgraph is not literal.node._pgraph:
                    raise ValueError('Must belong to the same Pgraph')
                literal.neglasts[neglast] = index

    def equivalent_all(self, others, why_therefore=None, why_becauseof=None):
        """Group equivalence: self <=> all(others)"""

        others = to_nvdict(others)

        self.therefore_all(others, why_therefore)
        self.becauseof_all(others, why_becauseof)

    def __repr__(self):
        return "%r=%r" % (self.node, self.value)

class Neglast(object):
    """
    Neglast unites a set of literals, that can't coexist all together: at
    least one of them must be negated. Neglast = NEGate the LAST left literal.
    """
    __slots__ = 'default', 'literals', 'why'

    def __init__(self, default, literals, why):
        super(Neglast, self).__init__()

        literals = to_lset(literals)

        if ~default in literals:
            raise ValueError('default conflicts with other literals')
        literals.add(default)

        self.default = default
        self.literals = literals
        self.why = why

    def neg_reason_for(self, last_literal=None):
        if last_literal is None:
            last_literal = self.default

        neg_literal = ~last_literal

        reason = Reason(self.why, neg_literal,
                        *(literal for literal in self.literals
                          if literal is not last_literal))

        if len(reason.cause_literals) != len(self.literals)-1:
            raise ValueError('last_literal must belong to this neglast')

        return neg_literal, reason


class Reason(namedtuple('_Reason', 'why, literal, cause_literals')):
    """docstring for Reason"""

    def __new__(cls, why, literal, *cause_literals):
        if why is None:
            why = cls._fallback_why_func

        return super(Reason, cls).__new__(cls, why, literal, cause_literals)

    def _fallback_why_func(cls, literal, *cause_literals):
        return '%s <= %s' % (literal, cause_literals)


#
# Conversion between node-value mappings/pairs and literals, and vice-versa.
#

def _do_check(nvdict, nvpairs):
    if len(nvdict) != len(nvpairs):
        raise ValueError('Item(s) with conflicting node values detected')

def to_lset(mapping_pairs_or_literals, check=True):
    """
    Returns set of literals.
    """
    mpls = mapping_pairs_or_literals

    if isinstance(mpls, Mapping):
        mpls = iteritems(mpls)
        check = False

    literals = set(node[value] for node, value in mpls)

    if check:
        _do_check(dict(literals), literals)

    return literals

def to_nvdict(mapping_pairs_or_literals, check=True):
    """
    Returns node-value dictionary.
    """
    mpls = mapping_pairs_or_literals
    if isinstance(mpls, Mapping):
        check = False

    if check:
        # unpack literals, if needed
        mpls = set((node, value) for node, value in mpls)

    nvdict = dict(mpls)

    if check:
        _do_check(nvdict, mpls)

    return nvdict


#
# Core Node types (used in Pgraph).
#

class AtomicNode(Node):
    """Marker class for leaf nodes."""


@Pgraph.node_type
class Atom(AtomicNode):
    """To be extended by the client."""
    _costs = (0, 1)


class ConstNode(AtomicNode):
    """Constrains a node to take a constant value."""
    types = Pair(None, None)  # overwritten below
    const_value = None  # overridden by subclasses

    why_self_has_const_value = None

    def __repr__(self):
        return repr(self.const_value).upper()

    def __invert__(self):
        return self._pgraph.new_node(self.types[not self.const_value])


@Pgraph.node_type
class FalseConst(ConstNode): const_value = False
@Pgraph.node_type
class TrueConst(ConstNode):  const_value = True

ConstNode.types = Pair(FalseConst, TrueConst)


#
# Node types representing widely used logic elements.
#

class SingleOperandNode(Node):
    """A node with a single operand."""

    def __init__(self, operand):
        super(SingleOperandNode, self).__init__()
        self._operand = operand

    @classmethod
    def _canonical_args(cls, operand):
        return operand


class OperandSetNode(Node):
    """A node which may have an arbitrary set of unordered unique operands."""

    def __init__(self, *operands):
        super(OperandSetNode, self).__init__()
        self._operands = set(operands)

    @classmethod
    def _new(cls, *operands):
        operands = set(operands)

        new = None

        if not operands:
            new = cls._new_no_operands()

        elif len(operands) == 1:
            new = cls._new_one_operand(*operands)

        if new is None:
            new = super(OperandSetNode, cls)._new(*operands)

        return new

    @classmethod
    def _new_no_operands(cls):
        return None

    @classmethod
    def _new_one_operand(cls, operand):
        return None

    @classmethod
    def _canonical_args(cls, *operands):
        return frozenset(operands)

    def __repr__(self):
        return '%s(%s)' % (type(self).__name__,
                           ', '.join(map(repr, self._operands)))


class LatticeOpNode(OperandSetNode):
    """
    An operation with the following properties:
      - Associative: op(op(A, B), C) == op(A, op(B, C))
      - Commutative: op(A, B) == op(B, A)
      - Idempotent:  op(A, A) == op(A) == A

    Neutral elements:
      - Identity: op(Identity, A) == A; op() == Identity
      - Zero: op(Zero, A) == Zero

    """

    # Reason of '(self is Identity) => (each operand is Identity)' implication.
    why_self_identity_implies_all_operands_identity = None

    # Reason of 'op(Identity, A) == op(A) == A' for single operand case.
    why_self_zero_implies_at_least_one_operand_zero = None

    def __init__(self, *operands):
        super(LatticeOpNode, self).__init__(*operands)

        identity = self.identity
        self[identity].equivalent_all(dict.fromkeys(operands, identity),
            why_therefore=self.why_self_identity_implies_all_operands_identity,
            why_becauseof=self.why_self_zero_implies_at_least_one_operand_zero)

    @classmethod
    def _new(cls, *operands):
        identity_const_type = ConstNode.types[cls.identity]

        return super(LatticeOpNode, cls)._new(
            *(operand for operand in operands
              if not isinstance(operand, identity_const_type)))

    @classmethod
    def _new_no_operands(cls):
        return cls._pgraph.new_const(cls.identity)

    def __repr__(self):
        return self._repr_sign.join(map(repr, self._operands)).join('()')

@Pgraph.node_type
class And(LatticeOpNode):

    identity = True
    zero     = False

    _repr_sign = ' & '

@Pgraph.node_type
class Or(LatticeOpNode):

    identity = False
    zero     = True

    _repr_sign = ' | '


@Pgraph.node_type
class Not(SingleOperandNode):
    """
    Logical negation.

       op    self
    -----   -----
     True   False
    False    True
    """

    why_self_equals_negated_operand = None

    def __init__(self, operand):
        super(Not, self).__init__(operand)

        self[False].equivalent(operand[True],
                why_becauseof=self.why_self_equals_negated_operand)

    @classmethod
    def _new(cls, operand):
        if isinstance(operand, Not):
            return operand._operand
        elif isinstance(operand, ConstNode):
            return cls._pgraph.new_const(not operand.const_value)
        else:
            return super(Not, cls)._new(operand)

    def __repr__(self):
        return '(~%r)' % (self._operand,)


@Pgraph.node_type
class Implies(Node):
    """
    Simple logical implication.

       if    then    self
    -----   -----   -----
     True    True    True
     True   False   False
    False    True    True
    False   False    True
    """

    why_self_false_implies_if_true = None
    why_self_false_implies_then_false = None

    def __init__(self, if_, then):
        super(Implies, self).__init__()

        self._if = if_
        self._then = then

        self[False].equivalent_all({if_:True, then:False}) # XXX reasons

    @classmethod
    def _new(cls, if_, then):
        # if (isinstance(if_, FalseConstNode) or
        #       isinstance(then, TrueConstNode)):
        #     return cls._pgraph.new_const(True)

        # elif isinstance(if_, TrueConstNode):
        #     return then

        # elif isinstance(then, FalseConstNode):
        #     return cls._pgraph.new_node(Not, if_)

        return super(Implies, cls)._new(if_, then)

    @classmethod
    def _canonical_args(cls, if_, then):
        return if_, then

    def __repr__(self):
        return '(%r => %r)' % (self._if, self._then)


class SingleZeroLatticeOpNode(LatticeOpNode):
    """
    Allows at most a single operand to be Zero, the rest must be Identity.
    """

    why_one_operand_zero_implies_others_identity = None

    def __init__(self, *operands):
        super(SingleZeroLatticeOpNode, self).__init__(*operands)

        # this introduces N^2 imlications between operands, uff...
        for operand in operands:
            operand[self.zero].therefore_all((another[self.identity]
                                              for another in operands
                                              if another is not operand),
                why=self.why_one_operand_zero_implies_others_identity)


@Pgraph.node_type
class AtMostOne(SingleZeroLatticeOpNode, Or):
    """
    Like Or, but allows at most a single operand to be True.

      op1     ...     opN    self
    -----   -----   -----   -----
     True   False   False    True
    False   False   False   False

    When there is no operands, evaluates to False.
    """

@Pgraph.node_type
class AllEqual(OperandSetNode):
    """
    Forces all operands to take the same value, and evaluates to that value.
    May be considered as a common alias for its operands.

      op1     ...     opN    self
    -----   -----   -----   -----
     True    True    True    True
    False   False   False    False
    """

    why_self_equals_all_operands = None

    def __init__(self, *operands):
        super(AllEqual, self).__init__(*operands)

        for operand in operands:
            self[False].equivalent(operand[False],
                                   why=self.why_self_equals_all_operands)

    @classmethod
    def _new_one_operand(cls, operand):
        return operand


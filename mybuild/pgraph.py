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


from _compat import *

from collections import namedtuple
from operator import attrgetter

from util.misc import bools
from util.misc import Pair
from util.operator import instanceof
from util.collections import is_mapping


class PgraphMeta(type):

    def __init__(cls, name, bases, attrs):
        super(PgraphMeta, cls).__init__(name, bases, attrs)
        cls._registered_node_types = set()

    def node_type(cls, target):
        if not (isinstance(target, type) and
                issubclass(target, NodeBase)):
            raise TypeError('Deco must be applied to a subclass '
                            'of NodeBase, got %s object instead: %r' %
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


class Pgraph(extend(metaclass=PgraphMeta)):
    """docstring for Pgraph"""

    nodes = property(lambda self: set(itervalues(self._node_map)))

    @property
    def atoms(self):
        return [node for node in self.nodes if isinstance(node, Atom)]

    def __init__(self):
        super(Pgraph, self).__init__()

        node_types = self._node_types = {}
        for node_type in type(self)._iter_all_node_types():
            bases = self._node_type_bases(node_type)
            node_types[node_type] = type(node_type.__name__, bases,
                                         dict(pgraph=self))

        self._node_map = {}

        self.const_literals = Pair._make(
                self.new_node(ConstNode.types[const_value])[const_value]
                for const_value in bools)

    def _node_type_bases(self, node_type):
        return (node_type,)

    def new_node(self, node_type, *args, **kwargs):
        """
        Returns a node of the given type.

        All nodes are cached and subsequent calls with the same arguments will
        return the same object.
        """
        try:
            cls = self._node_types[node_type]

        except KeyError:
            raise TypeError('Must register %s class using @%s.node_type' %
                            (node_type.__name__, type(self).__name__))

        else:
            return cls._new(*args, **kwargs)

    def new_const(self, const_value, node=None, why=None):
        """
        Constrains a given node (if any) to the specified const_value.
        In case if node is None, returns a special constant node.
        """
        const_literal = self.const_literals[const_value]

        if node is not None:
            node[const_value].becauseof(const_literal, why)
        else:
            node = const_literal.node

        return node


class NodeMeta(type):
    """
    Allows a Node to be instantiated as usual by passing a pgraph instance
    as the first argument.
    """

    def __call__(cls, pgraph, *args, **kwargs):
        return pgraph.new_node(cls, *args, **kwargs)

    def _factory_call(cls, *args, **kwargs):
        return super(NodeMeta, cls).__call__(*args, **kwargs)


class NodeBase(extend(metaclass=NodeMeta)):
    """
    Subclasses may want to overload NodeBase._new classmethod to customize
    instance creation instead of using __new__.
    """
    __slots__ = ()

    @classmethod
    def _new(cls, *args, **kwargs):
        try:
            pgraph = cls.pgraph
        except AttributeError:
            raise TypeError("Don't instantiate this class directly, "
                            "use pgraph.new_node(%s, ...) instead" %
                            cls.__name__)
        else:
            cache = pgraph._node_map

        if kwargs.pop('cache_kwargs', False):
            cache_kwargs = frozenset(iteritems(kwargs))
        else:
            cache_kwargs = None

        cache_key = cls, args, cache_kwargs
        try:
            ret = cache[cache_key]
        except KeyError:
            ret = cache[cache_key] = cls._factory_call(*args, **kwargs)

        return ret


class Node(NodeBase, Pair):
    """
    Each node is effectively a pair of two literals:
    one for False, and one for True. See Literal class below.
    """
    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        new_node = super(Node, cls).__new__(cls,
                                            false=Literal(), true=Literal())

        for literal in new_node:
            literal.node = new_node

        assert all(new_node[bool_value].value == bool_value
                   for bool_value in bools)

        return new_node

    def implies(self, other, why=None):
        self[True].therefore(other[True], why)

    def equivalent(self, other, why_therefore=None, why_becauseof=None):
        self[True].equivalent(other[True], why_therefore, why_becauseof)

    def implies_all(self, others, why=None):
        self[True].therefore_all(dict.fromkeys(others, True), why)

    def equivalent_all(self, others, why_therefore=None, why_becauseof=None):
        self[True].equivalent_all(dict.fromkeys(others, True),
                                  why_therefore, why_becauseof)


class Literal(object):
    """
    Depending on a node value the node may behave differently.
    Literal object describes such behavior.

    Literal object is tightly related to its node. Do not construct it
    manually.
    """
    __slots__ = 'node', 'level', 'implies', 'imply_reasons', 'neglasts'

    pgraph = property(attrgetter('node.pgraph'))
    value  = property(lambda self: self is self.node[True])

    def __init__(self):
        super(Literal, self).__init__()
        # node property is initialized by the Node itself

        self.level = None

        self.implies       = set()  # what to include among with this one
        self.imply_reasons = set()  # precreated reason objects
        self.neglasts      = set()  # from where to exclude

    def __invert__(self):
        """Returns the opposite literal."""
        return self.node[not self.value]

    def __iter__(self):
        """Support for tuple unpacking: (node, value)"""
        return iter((self.node, self.value))

    def __getitem__(self, item):
        """Returns the opposite literal."""
        return (self if bools[item] else ~self)  # bools if for type check

    @staticmethod
    def __imply(if_, then, why=None):
        if_.implies.add(then)
        if_.imply_reasons.add(Reason(then, [if_], why))

    def therefore(self, other, why=None):
        """Implication: self => other"""

        if self is other:
            return

        if self is ~other:
            raise ValueError('Implication of self negation')

        if self.node.pgraph is not other.node.pgraph:
            raise ValueError('Must belong to the same Pgraph')

        self.__imply(self,   other,  why)
        self.__imply(~other, ~self,  why)

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

        node_values = dict(to_lset(others))
        if node_values.pop(self.node, self.value) is not self.value:
            raise ValueError('Implication of self negation')

        if not node_values:
            self.node.pgraph.new_const(self.value, self.node, why)

        elif len(node_values) == 1:
            node, value = node_values.popitem()
            self.becauseof(node[value], why)

        else:
            neglast = Neglast(~self, node_values, why)

            for literal in neglast.literals:
                if self.node.pgraph is not literal.node.pgraph:
                    raise ValueError('Must belong to the same Pgraph')
                literal.neglasts.add(neglast)

    def equivalent_all(self, others, why_therefore=None, why_becauseof=None):
        """Group equivalence: self <=> all(others)"""

        others = to_lset(others)

        self.therefore_all(others, why_therefore)
        self.becauseof_all(others, why_becauseof)

    def __lshift__(self, other):
        self.becauseof(other)
        return other

    def __rshift__(self, other):
        self.therefore(other)
        return other

    def __repr__(self):
        return "%s%r" % ('' if self.value else '~', self.node)
        # return "%r=%r" % (self.node, self.value)


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

        reason = Reason(neg_literal, (literal for literal in self.literals
                                      if literal is not last_literal),
                        self.why)

        if len(reason.cause_literals) != len(self.literals)-1:
            raise ValueError('last_literal must belong to this neglast')

        return neg_literal, reason

    def __repr__(self):
        return ('<{cls.__name__}: {nr_literals} literals, {default}>'
                .format(cls=type(self),
                        nr_literals=len(self.literals), default=self.default))

class Reason(namedtuple('_Reason', 'literal, cause_literals, why, follow')):
    """docstring for Reason"""

    def __new__(cls, literal, cause_literals=[], why=None, follow=False):
        if why is None:
            why = cls.default_why_func

        return super(Reason, cls).__new__(cls, literal, tuple(cause_literals),
                                          why, follow)

    @classmethod
    def default_why_func(cls, outcome, *causes):
        cause_str = ' + '.join(map(str, causes)) or 'no cause'
        return '%s <= (%s)' % (outcome, cause_str)

    def __repr__(self):
        return self.why(self.literal, *self.cause_literals)


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

    if is_mapping(mpls):
        mpls = iteritems(mpls)

    literals = set(node[value] for node, value in mpls)

    if check:
        _do_check(dict(literals), literals)

    return literals


#
# Core Node types (used in Pgraph).
#

class AtomicNode(Node):
    """Marker class for leaf nodes."""
    __slots__ = ()


@Pgraph.node_type
class Atom(AtomicNode):
    """To be extended by the client."""
    __slots__ = ()


class ConstNode(AtomicNode):
    """Constrains a node to take a constant value."""
    __slots__ = ()

    types = Pair(None, None)  # overwritten below
    const_value = None  # overridden by subclasses

    why_self_has_const_value = None

    def __repr__(self):
        return repr(self.const_value).upper()

    def __invert__(self):
        return self.pgraph.new_node(self.types[not self.const_value])


@Pgraph.node_type
class FalseConst(ConstNode): __slots__ = (); const_value = False

@Pgraph.node_type
class TrueConst(ConstNode):  __slots__ = (); const_value = True

ConstNode.types = Pair(FalseConst, TrueConst)


#
# Node types representing widely used logic elements.
#

class SingleOperandNode(Node):
    """A node with a single operand."""

    def __init__(self, operand, *args, **kwargs):
        super(SingleOperandNode, self).__init__(*args, **kwargs)
        self._operand = operand


class OperandSetNode(Node):
    """A node which may have an arbitrary set of unordered unique operands."""

    def __init__(self, operands, *args, **kwargs):
        super(OperandSetNode, self).__init__(*args, **kwargs)
        self._operands = operands

    @classmethod
    def _new(cls, operands, *args, **kwargs):
        operands = frozenset(operands)

        if not operands:
            new = cls._new_no_operands(*args, **kwargs)
        elif len(operands) == 1:
            operand, = operands
            new = cls._new_one_operand(operand, *args, **kwargs)
        else:
            new = None

        if new is None:
            new = super(OperandSetNode, cls)._new(operands, *args, **kwargs)

        return new

    @classmethod
    def _new_no_operands(cls, *args, **kwargs):
        pass

    @classmethod
    def _new_one_operand(cls, operand, *args, **kwargs):
        pass

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

    _optimize_new = False

    def __init__(self, operands, *args, **why_kwargs):
        why_therefore = why_kwargs.pop(
                'why_identity_implies_all_operands_identity', None)
        why_becauseof = why_kwargs.pop(
                'why_all_operands_identity_implies_identity', None)

        super(LatticeOpNode, self).__init__(operands, *args, **why_kwargs)

        identity = self.identity
        self[identity].equivalent_all(dict.fromkeys(operands, identity),
                                      why_therefore, why_becauseof)

    @classmethod
    def _new(cls, operands, *args, **kwargs):
        if cls._optimize_new:
            identity_const_type = ConstNode.types[cls.identity]
            operands = filternot(instanceof(identity_const_type), operands)

        return super(LatticeOpNode, cls)._new(operands, *args, **kwargs)

    @classmethod
    def _new_no_operands(cls, *args, **kwargs):
        if cls._optimize_new:
            return cls.pgraph.new_const(cls.identity)

    @classmethod
    def _new_one_operand(cls, operand, *args, **kwargs):
        if cls._optimize_new:
            return operand

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

    def __init__(self, operand, *args, **why_kwargs):
        why = why_kwargs.pop('why_self_equals_negated_operand', None)

        super(Not, self).__init__(operand, *args, **why_kwargs)

        self[False].equivalent(operand[True],
                               why_becauseof=why,
                               why_therefore=why)

    @classmethod
    def _new(cls, operand, *args, **kwargs):
        if isinstance(operand, Not):
            return operand._operand
        elif isinstance(operand, ConstNode):
            return cls.pgraph.new_const(not operand.const_value)
        else:
            return super(Not, cls)._new(operand, *args, **kwargs)

    def __repr__(self):
        return '!%r' % (self._operand,)


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

    def __init__(self, if_, then, *args, **why_kwargs):
        super(Implies, self).__init__(*args, **why_kwargs)

        self._if = if_
        self._then = then

        self[False].equivalent_all({if_: True, then: False})  # XXX reasons

    @classmethod
    def _new(cls, if_, then, *args, **kwargs):
        # if (isinstance(if_, FalseConstNode) or
        #       isinstance(then, TrueConstNode)):
        #     return cls.pgraph.new_const(True)

        # elif isinstance(if_, TrueConstNode):
        #     return then

        # elif isinstance(then, FalseConstNode):
        #     return cls.pgraph.new_node(Not, if_)

        return super(Implies, cls)._new(if_, then, *args, **kwargs)

    def __repr__(self):
        return '(%r => %r)' % (self._if, self._then)


class SingleZeroLatticeOpNode(LatticeOpNode):
    """
    Allows at most a single operand to be Zero, the rest must be Identity.
    """

    def __init__(self, operands, *args, **why_kwargs):
        why = why_kwargs.pop('why_one_operand_zero_implies_others_identity',
                             None)
        super(SingleZeroLatticeOpNode, self).__init__(operands,
                                                      *args, **why_kwargs)

        # this introduces N^2 imlications between operands, uff...
        for operand in operands:
            operand[self.zero].therefore_all(
                    (another[self.identity]
                     for another in operands
                     if another is not operand), why)


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

    def __init__(self, operands, *args, **why_kwargs):
        why = why_kwargs.pop('why_self_equals_all_operands', None)

        super(AllEqual, self).__init__(operands, *args, **why_kwargs)

        for operand in operands:
            self.equivalent(operand,
                            why_becauseof=why,
                            why_therefore=why)


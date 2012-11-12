"""
Boolean expessions.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-10-28"

__all__ = [
    "exprify",
    "exprify_eval",
    "ExprVisitor",
    "Expr",
    "And",
    "Or",
    "Not",
    "Atom",
]


from itertools import imap
from operator import attrgetter

from util import singleton


def exprify(something):
    if hasattr(something, '_to_expr'):
        return something._to_expr()
    if isinstance(something, int) and -2 <= something < 2:
        if something < 0:
            something = not ~something
        return bool(something)
    raise TypeError(
        "'something' must be either True, False, ~True, ~False, "
        "or another expression, got '%s' object instead" % type(something))

def exprify_eval(something, *args, **kwargs):
    expr = exprify(something)
    return expr if isinstance(expr, bool) else expr.eval(*args, **kwargs)


class Expr(object):
    """docstring for Expr"""

    class __metaclass__(type):
        """Avoids the need to set empty __slots__ on each subclass manually."""
        def __new__(cls, name, bases, attrs):
            attrs.setdefault('__slots__', ())
            attrs.setdefault('_visitor_method_name', name)
            return type.__new__(cls, name, bases, attrs)

    def eval(self, *args, **kwargs):
        raise NotImplementedError

    def atoms(self):
        return set(self._iter_atoms())

    def _iter_atoms(self):
        raise NotImplementedError

    def _to_expr(self):
        return self

    def __and__(self, other):
        """Overload for &"""
        try:
            other_expr = exprify(other)
        except TypeError:
            return NotImplemented
        else:
            return And(other_expr, self)
    __rand__ = __and__

    def __or__(self, other):
        """Overload for |"""
        try:
            other_expr = exprify(other)
        except TypeError:
            return NotImplemented
        else:
            return Or(other_expr, self)
    __ror__ = __or__

    def __invert__(self):
        """Overload for ~"""
        return Not(self)


class ExprVisitor(object):
    """Base class for expression visitors."""
    __slots__ = ()

    def visit(self, expr, *args, **kwargs):
        expr = exprify(expr)

        method_name = 'bool' if isinstance(expr, bool) else \
            expr._visitor_method_name
        method = getattr(self, 'visit_' + method_name)

        return method(expr, *args, **kwargs)

    def visit_And(self, expr, *args, **kwargs):
        for op in expr.operands: self.visit(op, *args, **kwargs)
    def visit_Or(self, expr, *args, **kwargs):
        for op in expr.operands: self.visit(op, *args, **kwargs)

    def visit_Not(self, expr, *args, **kwargs):
        self.visit(expr.atom, *args, **kwargs)

    def visit_Atom(self, expr, *args, **kwargs):
        pass

    def visit_bool(self, expr, *args, **kwargs):
        pass


class _LatticeOp(Expr):
    """Associative, commutative and idempotent operation."""
    __slots__ = '_operands'

    operands = property(attrgetter('_operands'))

    def __new__(cls, *exprs):
        return cls._from_iterable(exprs)

    @classmethod
    def _from_iterable(cls, exprs):
        zero = not cls._identity

        operands = set()
        for expr in exprs:
            expr = exprify(expr)
            if isinstance(expr, bool):
                if expr is zero:
                    return zero
            elif isinstance(expr, cls):
                operands.update(expr._operands)
            else:
                operands.add(expr)

        if not operands:
            return cls._identity
        if len(operands) == 1:
            return iter(operands).next()

        if not operands.isdisjoint(imap(Not, operands)):
            return zero

        ret = super(_LatticeOp, cls).__new__(cls)
        ret._operands = tuple(sorted(operands,
            key=lambda e: not isinstance(e, _AtomicExpr)))
        return ret

    def eval(self, *args, **kwargs):
        return self._from_iterable(
            op.eval(*args, **kwargs) for op in self._operands)

    def _iter_atoms(self):
        return (atom for op in self._operands for atom in op._iter_atoms())

    def __eq__(self, other):
        return type(self) == type(other) and self._operands == other._operands
    def __hash__(self):
        return hash(type(self)) ^ hash(self._operands)

    def __repr__(self):
        return self._repr_sign.join(map(repr, self._operands)).join('()')

class And(_LatticeOp):
    _identity = True
    _repr_sign = '&'

class Or(_LatticeOp):
    _identity = False
    _repr_sign = '|'


class _AtomicExpr(Expr):
    """Leaf expressions: Atom, Not(Atom)."""

    atom = property()

    def _iter_atoms(self):
        yield self.atom

class Not(_AtomicExpr):
    __slots__ = '_atom'

    atom = property(attrgetter('_atom'))

    @singleton
    class _new_visitor(ExprVisitor):
        def __call__(self, outer_cls, expr):
            return self.visit(expr, cls)
        def visit_Not(self, expr, cls):
            return expr._atom
        # de Morgan laws
        def visit_And(self, expr, cls):
            return Or._from_iterable(imap(Not, expr.operands))
        def visit_Or(self, expr, cls):
            return And._from_iterable(imap(Not, expr.operands))

        def visit_bool(self, expr, cls):
            return not expr

        def visit_Atom(self, expr, cls):
            ret = super(Not, cls).__new__(cls)
            ret._atom = expr
            return ret

    def __new__(cls, expr):
        return cls._new_visitor.visit(expr, cls)

    def eval(self, *args, **kwargs):
        return Not(self._atom.eval(*args, **kwargs))

    def __eq__(self, other):
        return isinstance(other, Not) and self._atom == other._atom
    def __hash__(self):
        return ~hash(self._atom)

    def __repr__(self):
        return '~%r' % self._atom

class Atom(_AtomicExpr):
    """To be extended by the client."""

    class __metaclass__(Expr.__metaclass__):
        def __new__(cls, name, bases, attrs):
            # bypass Expr.__metaclass__ to not confuse subclasses.
            return type.__new__(cls, name, bases, attrs)

    __slots__ = ()
    _visitor_method_name = 'Atom'

    atom = property(lambda self: self)

    def eval(self, *args, **kwargs):
        return self


if __name__ == '__main__':
    A,B,C = (Atom() for _ in xrange(3))
    # A.eval_value = False
    # import pdb; pdb.set_trace()
    print exprify_eval(C&(A|B)|C)

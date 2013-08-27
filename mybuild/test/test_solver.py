from _compat import *

import unittest
import functools

from mybuild import pgraph
from mybuild.solver import *


class TestPgraph(pgraph.Pgraph):

    def __init__(self):
        super(TestPgraph, self).__init__()

        for node_type in type(self)._iter_all_node_types():
            if not hasattr(self, node_type.__name__):
                setattr(self, node_type.__name__,
                        functools.partial(self.new_node, node_type))


class Named(object):

    @classmethod
    def _new(cls, *args, **kwargs):
        kwargs.setdefault('cache_kwargs', True)
        return super(Named, cls)._new(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        self._name = kwargs.pop('name', None)
        super(Named, self).__init__(*args, **kwargs)

    def __repr__(self):
        return self._name or super(Named, self).__repr__()


@TestPgraph.node_type
class NamedAtom(Named, pgraph.Atom):
    pass


class StarArgsToArg(object):
    """For compatibility with tests, to let them to pass operands in *args."""
    @classmethod
    def _new(cls, *operands, **kwargs):
        return super(StarArgsToArg, cls)._new(operands, **kwargs)


@TestPgraph.node_type
class Or(Named, StarArgsToArg, pgraph.Or):
    pass
@TestPgraph.node_type
class And(Named, StarArgsToArg, pgraph.And):
    pass

@TestPgraph.node_type
class AtMostOne(Named, StarArgsToArg, pgraph.AtMostOne):
    pass
@TestPgraph.node_type
class AllEqual(Named, StarArgsToArg, pgraph.AllEqual):
    pass


class SolverTestCaseBase(unittest.TestCase):

    def setUp(self):
        self.pgraph = TestPgraph()

    def atoms(self, names):
        return [self.pgraph.NamedAtom(name=name) for name in names]


class TrunkTestCase(SolverTestCaseBase):
    """Test cases which do not involve branching."""

    def test_initial_const(self):
        g = self.pgraph
        A, = self.atoms('A')

        N = g.new_const(True, A)
        solution = solve(g, {})

        self.assertIs(True, solution[A])

    def test_implication_1(self):
        g = self.pgraph
        A, = self.atoms('A')

        N = g.Not(A)
        solution = solve(g, {N: True})

        self.assertIs(True,  solution[N])
        self.assertIs(False, solution[A])

    def test_implication_2(self):
        g = self.pgraph
        A,B,C = self.atoms('ABC')

        N = g.AtMostOne(A,B,C)
        solution = solve(g, {N: False})

        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_implication_3(self):
        g = self.pgraph
        A,B,C = self.atoms('ABC')

        N = g.AtMostOne(A,B,C)
        solution = solve(g, {N: True, A: True})

        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_neglast_1(self):
        g = self.pgraph
        A,B,C,D = self.atoms('ABCD')

        # (A|B) & (C|D) & (B|~C) & ~B
        N = g.And(g.Or(A,B), g.Or(C,D), g.Or(B, g.Not(C)), g.Not(B))
        solution = solve(g, {N: True})

        self.assertIs(True,  solution[N])
        self.assertIs(True,  solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])
        self.assertIs(True,  solution[D])

    def test_neglast_2(self):
        g = self.pgraph
        A,B = self.atoms('AB')

        # (A=>B) & A
        N = g.And(g.Implies(A,B), A)
        solution = solve(g, {N: True})

        self.assertIs(True,  solution[N])
        self.assertIs(True,  solution[A])
        self.assertIs(True,  solution[B])

    def test_neglast_3(self):
        g = self.pgraph
        A,B = self.atoms('AB')

        # (A=>B) & ~B
        N = g.And(g.Implies(A,B), g.Not(B))
        solution = solve(g, {N: True})

        self.assertIs(True,  solution[N])
        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])

    def test_neglast_4(self):
        g = self.pgraph
        A,B,C = self.atoms('ABC')

        N = g.AtMostOne(A,B,C)
        solution = solve(g, {N: True, A: False, B: False})

        self.assertIs(True, solution[C])

    def test_violation_1(self):
        g = self.pgraph
        A, = self.atoms('A')

        # A & ~A
        N = g.And(A, g.Not(A))

        with self.assertRaises(SolveError):
            solve(g, {N: True})

    def test_violation_2(self):
        g = self.pgraph
        A,B,C = self.atoms('ABC')

        N = g.AtMostOne(A,B,C)
        with self.assertRaises(SolveError):
            solve(g, {A: True, B: True})


class BranchTestCase(SolverTestCaseBase):

    def sneaky_pair_and(self, a, b, **kwargs):
        """(A | B) & (~A | B) & (A | ~B)"""
        g = self.pgraph
        # return g.And(g.Or(a,        b),
        #              g.Or(g.Not(a), b),
        #              g.Or(a, g.Not(b)), **kwargs)

        # solved the same way as an expr above, but gives lesser logs
        return g.And(g.Or(a[True],  b[True]),
                     g.Or(a[False], b[True]),
                     g.Or(a[True], b[False]), **kwargs)

    def sneaky_chain(self):
        g = self.pgraph
        A, B, C, D, E = self.atoms('ABCDE')

        #     (E | Z) & (~E | Z) & (E | ~Z), where
        # Z = (D | Y) & (~D | Y) & (D | ~Y), where
        # Y = (C | X) & (~C | X) & (C | ~X), where
        # X = (A | B) & (~A | B) & (A | ~B)
        X = self.sneaky_pair_and(A, B, name='X')
        Y = self.sneaky_pair_and(C, X, name='Y')
        Z = self.sneaky_pair_and(D, Y, name='Z')
        P = self.sneaky_pair_and(E, Z)

        return P, (X, Y, Z), (A, B, C, D, E)

    def test_contradiction_1(self):
        g = self.pgraph
        A,B = self.atoms('AB')

        # (A|B) & (~A | A&~A)
        N = g.And(g.Or(A, B), g.Or(g.Not(A), g.And(A, g.Not(A))))
        solution = solve(g, {N: True})

        self.assertIs(False, solution[A])
        self.assertIs(True,  solution[B])

    def test_contradiction_2(self):
        g = self.pgraph
        A,B = self.atoms('AB')
        nA,nB = map(g.Not, (A,B))

        # (A + ~A&~B + ~B) & (B + B&~A)
        # solution = solve(g, {N: True})
        solution = solve(g, {
                g.Or(A, g.And(nA, nB), nB): True,
                g.Or(B, g.And(nA, B)): True
            })

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    def test_15(self):
        g = self.pgraph
        A,B,C = self.atoms('ABC')

        # (A | A&~A) & (A=>B) & (B=>C) & (C=>A)
        A[True] >> B[True] >> C[True] >> A[True]
        N = g.Or(A, g.And(A, g.Not(A)))
        solution = solve(g, {N: True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])

    def test_resolve_0(self):
        g = self.pgraph
        A, B = self.atoms('AB')

        x = g.And(B[False], A[False], g.Or(A[True], B[True]))
        y = B[True]
        x.equivalent(y)

        with self.assertRaises(SolveError):
            solve(g, {self.sneaky_pair_and(A, B): True})

    def test_resolve_1(self):
        g = self.pgraph
        A, B = self.atoms('AB')

        solution = solve(g, {self.sneaky_pair_and(A, B): True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    def test_resolve_2(self):
        g = self.pgraph
        A, B, C = self.atoms('ABC')

        #     (C | X) & (~C | X) & (C | ~X), where
        # X = (A | B) & (~A | B) & (A | ~B)
        X = self.sneaky_pair_and(A, B, name='X')
        P = self.sneaky_pair_and(C, X)

        solution = solve(g, {P: True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])
        self.assertIs(True, solution[X])

    def test_resolve_4(self):
        g = self.pgraph

        P, pair_ands, atoms = self.sneaky_chain()

        solution = solve(g, {P: True})

        for node in (pair_ands + atoms):
            self.assertIs(True, solution[node], "{0} is not True".format(node))

    def test_trunk_base(self):
        g = self.pgraph

        P, pair_ands, atoms = self.sneaky_chain()

        initial_trunk = create_trunk(g, {P: True})
        solved_trunk  = solve_trunk(g, {P: True})

        self.assertEqual(Solution(initial_trunk), solved_trunk.base)
        self.assertEqual(initial_trunk.base, solved_trunk.base)


if __name__ == '__main__':
    import util, sys, logging
    # util.init_logging(filename='%s.log' % __name__)
    util.init_logging(sys.stderr,
                      level=logging.INFO)

    unittest.main(verbosity=2)


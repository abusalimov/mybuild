import unittest
from unittest import TestCase

from functools import partial
from itertools import izip_longest

from mybuild.solver import *
from mybuild.pgraph import *


class TestPgraph(Pgraph):

    def __init__(self):
        super(TestPgraph, self).__init__()

        for node_type in type(self)._iter_all_node_types():
            setattr(self, node_type.__name__,
                    partial(self.new_node, node_type))


@TestPgraph.node_type
class NamedAtom(Atom):
    def __init__(self, name):
        super(NamedAtom, self).__init__()
        self.name = name
    def __repr__(self):
        return self.name

@TestPgraph.node_type
class NamedAtomWithCost(NamedAtom):
    def __init__(self, name, cost=0):
        super(NamedAtomWithCost, self).__init__(name)
        self.cost = cost
    def __repr__(self):
        return '%s(%s)' % (self.name, self.cost)


class PdagDtreeTestCase(TestCase):

    def setUp(self):
        self.pgraph = TestPgraph()

    @classmethod
    def atoms(cls, pgraph, names, costs=()):
        atom, atom_with_cost = pgraph.NamedAtom, pgraph.NamedAtomWithCost
        return [atom_with_cost(name or '', cost) if cost is not None else
                atom(name) for name, cost in izip_longest(names, costs)]
         
    def test_00(self):
        g = self.pgraph
        A, = self.atoms(g, 'A')

        pnode = g.Not(A)
        solution = solve(g, {pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(False, solution[A])

    def test_01(self):
        g = self.pgraph
        A,B,C,D = self.atoms(g, 'ABCD')

        # (A|B) & (C|D) & (B|~C) & ~B
        pnode = g.And(g.Or(A,B), g.Or(C,D), g.Or(B, g.Not(C)), g.Not(B))
        solution = solve(g, {pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(True,  solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])
        self.assertIs(True,  solution[D])

    def test_02(self):
        g = self.pgraph
        A,B = self.atoms(g, 'AB')

        # (A|B) & (~A|B) & (A|~B)
        pnode = g.And(g.Or(A,B), g.Or(g.Not(A), B), g.Or(A, g.Not(B)))
        solution = solve(g, {pnode:True})

        self.assertIs(True, solution[pnode])
        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    def test_03(self):
        g = self.pgraph
        A, = self.atoms(g, 'A')

        # A & ~A
        pnode = g.And(A, g.Not(A))

        with self.assertRaises(SolveError):
            solve(g, {pnode:True})

    def test_04(self):
        g = self.pgraph
        A,B = self.atoms(g, 'AB')

        # (A|B) & (~A | A&~A)
        pnode = g.And(g.Or(A, B), g.Or(g.Not(A), g.And(A, g.Not(A))))
        solution = solve(g, {pnode:True})

        self.assertIs(False, solution[A])
        self.assertIs(True,  solution[B])

    def test_05(self):
        g = self.pgraph
        A,B = self.atoms(g, 'AB')
        nA,nB = map(g.Not, (A,B))

        # (A + ~A&~B + ~B) & (B + B&~A)
        # solution = solve(g, {pnode:True})
        solution = solve(g, {
                g.Or(A, g.And(nA, nB), nB): True,
                g.Or(B, g.And(nA, B)): True
            })

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    @unittest.skip("NIY")
    def test_06(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')
        nA,nB,nC = map(g.Not, (A,B,C))

        # (A+B+C)&(~A+B+C)&(A+~B+C)&(A+B+~C)&(~A+~B+C)&(A+~B+~C)&(~A+B+~C)
        pnode = g.And(
            g.Or( A, B, C),
            g.Or(nA, B, C),
            g.Or( A,nB, C),
            g.Or( A, B,nC),
            g.Or( A,nB,nC),
            g.Or(nA, B,nC),
            g.Or(nA,nB, C),
        )
        solution = solve(g, {pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])

    @unittest.skip("Outputs too much when loing is on")
    def test_07(self):
        g = self.pgraph
        A,B,C,D,E = self.atoms(g, 'ABCDE')
        nA,nB,nC,nD,nE = map(g.Not, (A,B,C,D,E))

        # the same as test_06 but for 5 variables
        pnode = g.And(
            g.Or( A, B, C, D, E),

            g.Or(nA, B, C, D, E),
            g.Or( A,nB, C, D, E),
            g.Or( A, B,nC, D, E),
            g.Or( A, B, C,nD, E),
            g.Or( A, B, C, D,nE),

            g.Or(nA,nB, C, D, E),
            g.Or( A,nB,nC, D, E),
            g.Or( A, B,nC,nD, E),
            g.Or( A, B, C,nD,nE),
            g.Or(nA, B, C, D,nE),

            g.Or(nA, B,nC, D, E),
            g.Or( A,nB, C,nD, E),
            g.Or( A, B,nC, D,nE),
            g.Or(nA, B, C,nD, E),
            g.Or( A,nB, C, D,nE),

            g.Or( A, B,nC,nD,nE),
            g.Or(nA, B, C,nD,nE),
            g.Or(nA,nB, C, D,nE),
            g.Or(nA,nB,nC, D, E),
            g.Or( A,nB,nC,nD, E),

            g.Or( A,nB, C,nD,nE),
            g.Or(nA, B,nC, D,nE),
            g.Or(nA,nB, C,nD, E),
            g.Or( A,nB,nC, D,nE),
            g.Or(nA, B,nC,nD, E),

            g.Or( A,nB,nC,nD,nE),
            g.Or(nA, B,nC,nD,nE),
            g.Or(nA,nB, C,nD,nE),
            g.Or(nA,nB,nC, D,nE),
            g.Or(nA,nB,nC,nD, E),
        )
        solution = solve(g, {pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])
        self.assertIs(True, solution[D])
        self.assertIs(True, solution[E])

    def test_08(self):
        g = self.pgraph
        A,B = self.atoms(g, 'AB')

        # (A=>B) & A
        pnode = g.And(g.Implies(A,B), A)
        solution = solve(g, {pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(True,  solution[A])
        self.assertIs(True,  solution[B])

    def test_09(self):
        g = self.pgraph
        A,B = self.atoms(g, 'AB')

        # (A=>B) & ~B
        pnode = g.And(g.Implies(A,B), g.Not(B))
        solution = solve(g, {pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])

    def test_10(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOne(A,B,C)
        solution = solve(g, {pnode:True, A:True})

        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_11(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOne(A,B,C)
        solution = solve(g, {pnode:True, A:False, B:False})

        self.assertIs(True, solution[C])

    def test_12(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOne(A,B,C)
        solution = solve(g, {pnode:False})

        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_13(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOne(A,B,C)
        with self.assertRaises(SolveError):
            solve(g, {A:True, B:True})

    def test_14(self):
        g = self.pgraph
        A, = self.atoms(g, 'A')

        pnode = g.new_const(True, A)
        solution = solve(g, {})

        self.assertIs(True, solution[A])

    def test_15(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')

        # (A | A&~A) & (A=>B) & (B=>C) & (C=>A)
        A[True] >> B[True] >> C[True] >> A[True]
        pnode = g.Or(A, g.And(A, g.Not(A)))
        solution = solve(g, {pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])
    
    @unittest.skip("Need make it work")    
    def test_16(self):
        g = self.pgraph
        A,B,C = self.atoms(g, 'ABC')
        nA,nB,nC = map(g.Not, (A,B,C))

        #(A | X) & (~A | X) & (A | ~X), where X = (B | C) & (~B | C) & (B | ~C)
        pnode = g.And(
            g.Or( A, g.And(g.Or(B, C), g.Or(nB, C), g.Or(B, nC))),
            g.Or(nA, g.And(g.Or(B, C), g.Or(nB, C), g.Or(B, nC))),
            g.Or( A, g.Not(g.And(g.Or(B, C), g.Or(nB, C), g.Or(B, nC)))),
        )
        solution = solve(g, {pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])


if __name__ == '__main__':
    import mybuild.logs as log

    log.zones = set([
                    'pgraph',
                    'dtree',
                    'solver'
                    ])
    log.verbose = True
    log.init_log()

    log.make_logger('solver.log', 'solver')

    unittest.main()


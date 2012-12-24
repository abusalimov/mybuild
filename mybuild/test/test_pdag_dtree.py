import unittest
from unittest import TestCase

from functools import partial
from itertools import izip_longest

from mybuild.dtree import *
from mybuild.pdag import *


class TestPdag(Pdag):

    def __init__(self):
        super(TestPdag, self).__init__()

        for node_type in type(self)._iter_all_node_types():
            setattr(self, node_type.__name__, partial(self.new, node_type))


@TestPdag.node_type
class NamedAtom(Atom):
    __slots__ = 'name'
    def __init__(self, name):
        super(NamedAtom, self).__init__()
        self.name = name
    def __repr__(self):
        return self.name

@TestPdag.node_type
class NamedAtomWithCost(NamedAtom):
    __slots__ = 'cost'
    def __init__(self, name, cost=0):
        super(NamedAtomWithCost, self).__init__(name)
        self.cost = cost
    def __repr__(self):
        return '%s(%s)' % (self.name, self.cost)


class PdagDtreeTestCase(TestCase):

    def setUp(self):
        self.pdag = TestPdag()

    @classmethod
    def atoms(cls, pdag, names, costs=()):
        new_atom, new_atom_with_cost = pdag.NamedAtom, pdag.NamedAtomWithCost
        return [new_atom_with_cost(name or '', cost) if cost is not None else
                new_atom(name) for name, cost in izip_longest(names, costs)]

    def test_1(self):
        g = self.pdag
        A,B,C,D = self.atoms(g, 'ABCD')

        # (A|B) & (C|D) & (B|~C) & ~B
        pnode = g.And(g.Or(A,B), g.Or(C,D), g.Or(B, g.Not(C)), g.Not(B))
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(True,  solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])
        self.assertIs(True,  solution[D])

    def test_2(self):
        g = self.pdag
        A,B = self.atoms(g, 'AB')

        # (A|B) & (~A|B) & (A|~B)
        pnode = g.And(g.Or(A,B), g.Or(g.Not(A), B), g.Or(A, g.Not(B)))
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True, solution[pnode])
        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    def test_3(self):
        g = self.pdag
        A, = self.atoms(g, 'A')

        # A & ~A
        pnode = g.And(A, g.Not(A))

        with self.assertRaises(PdagContextError):
            Dtree(g).solve({pnode:True})

    def test_4(self):
        g = self.pdag
        A,B = self.atoms(g, 'AB')

        # (A|B) & (~A | A&~A)
        pnode = g.And(g.Or(A, B), g.Or(g.Not(A), g.And(A, g.Not(A))))
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(False, solution[A])
        self.assertIs(True,  solution[B])

    def test_5(self):
        g = self.pdag
        A,B = self.atoms(g, 'AB')

        # (~A + A&B + B) & (~B + ~B&A)
        pnode = g.And(g.Or(g.Not(A), g.And(A,B), B),
                       g.Or(g.Not(B), g.And(A, g.Not(B))))
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])

    def test_6(self):
        g = self.pdag
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
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])

    @unittest.skip("Outputs too much when loing is on")
    def test_7(self):
        g = self.pdag
        A,B,C,D,E = self.atoms(g, 'ABCDE')
        nA,nB,nC,nD,nE = map(g.Not, (A,B,C,D,E))

        # the same as test_6 but for 5 variables
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
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])
        self.assertIs(True, solution[C])
        self.assertIs(True, solution[D])
        self.assertIs(True, solution[E])

    def test_8(self):
        g = self.pdag
        A,B = self.atoms(g, 'AB')

        # (A=>B) & A
        pnode = g.And(g.Implies(A,B), A)
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(True,  solution[A])
        self.assertIs(True,  solution[B])

    def test_9(self):
        g = self.pdag
        A,B = self.atoms(g, 'AB')

        # (A=>B) & ~B
        pnode = g.And(g.Implies(A,B), g.Not(B))
        solution = Dtree(g).solve({pnode:True})

        self.assertIs(True,  solution[pnode])
        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])

    def test_10(self):
        g = self.pdag
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOneConstraint(A,B,C)
        solution = Dtree(g).solve({pnode:True, A:True})

        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_11(self):
        g = self.pdag
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOneConstraint(A,B,C)
        solution = Dtree(g).solve({pnode:True, A:False, B:False})

        self.assertIs(True, solution[C])

    def test_12(self):
        g = self.pdag
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOneConstraint(A,B,C)
        solution = Dtree(g).solve({pnode:False})

        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])
        self.assertIs(False, solution[C])

    def test_13(self):
        g = self.pdag
        A,B,C = self.atoms(g, 'ABC')

        pnode = g.AtMostOneConstraint(A,B,C)
        with self.assertRaises(PdagContextError):
            Dtree(g).solve({A:True, B:True})

    def test_14(self):
        g = self.pdag
        A, = self.atoms(g, 'A')

        pnode = g.TrueConstraint(A)
        solution = Dtree(g).solve({})

        self.assertIs(True, solution[A])


if __name__ == '__main__':

    import mybuild.logs as log

    log.zones = set([
                    'pdag',
                    'dtree',
                    ])
    log.verbose = True
    log.init_log()


    unittest.main()


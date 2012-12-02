import unittest
from unittest import TestCase

from mybuild.dtree import *
from mybuild.pdag import *

class PdagDtreeTestCase(TestCase):

    class NamedAtom(Atom):
        __slots__ = 'name'
        def __init__(self, name):
            super(PdagDtreeTestCase.NamedAtom, self).__init__()
            self.name = name
        def __str__(self):
            return self.name

    def atoms(self, names):
        return [self.NamedAtom(nm) for nm in names]

    def test_1(self):
        A,B,C,D = self.atoms('ABCD')

        # (A|B) & (C|D) & (B|~C) & ~B
        pnode = And(Or(A,B), Or(C,D), Or(B, Not(C)), Not(B))
        dtree = DtreeNode()
        dtree[pnode] = True

        self.assertIs(True,  dtree[pnode])
        self.assertIs(True,  dtree[A])
        self.assertIs(False, dtree[B])
        self.assertIs(False, dtree[C])
        self.assertIs(True,  dtree[D])

    def test_2(self):
        A,B = self.atoms('AB')

        # (A|B) & (~A|B) & (A|~B)
        pnode = And(Or(A,B), Or(Not(A), B), Or(A, Not(B)))
        dtree = Dtree(Pdag(A, B))

        # for k,v in dtree._root._dict.items():
        #     print v, k, '***' if v is None else ''

        # print '=' * 40
        solution = dtree.solve({pnode:True})

        # for k,v in solution.items():
        #     print v, k, '***' if v is None else ''

        self.assertIs(True, solution[pnode])
        self.assertIs(True, solution[A])
        self.assertIs(True, solution[B])

    def test_3(self):
        A, = self.atoms('A')

        # A & ~A
        pnode = And(A, Not(A))
        dtree = Dtree(Pdag(A))

        with self.assertRaises(DtreeConflictError):
            dtree.solve({pnode:True})

    def test_4(self):
        A,B = self.atoms('AB')

        # (A|B) & (~A | A&~A)
        pnode = And(Or(A, B), Or(Not(A), And(A, Not(A))))
        dtree = Dtree(Pdag(A, B))

        solution = dtree.solve({pnode:True})

        self.assertIs(False, solution[A])
        self.assertIs(True,  solution[B])

    def test_5(self):
        A,B = self.atoms('AB')

        # (~A + A&B + B) & (~B + ~B&A)
        pnode = And(Or(Not(A), And(A,B), B), Or(Not(B), And(A, Not(B))))
        dtree = Dtree(Pdag(A, B))

        solution = dtree.solve({pnode:True})

        self.assertIs(False, solution[A])
        self.assertIs(False, solution[B])


if __name__ == '__main__':

    import mybuild.logs as log

    log.zones = set(['pdag'])
    log.verbose = True
    log.init_log()


    unittest.main()


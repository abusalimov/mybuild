import unittest
from unittest import TestCase

from mybuild.dsl.pyfile import module
from mybuild.context import Context
from mybuild.solver import solve

class PdagDtreeTestCase(TestCase):

    def test_simple_solution(self):
        context = Context()

        @module
        def conf(self):
            self.constrain(m1(isM2 = True))

        @module
        def m1(self, isM2 = False):
            if isM2:
                self.constrain(m2)

        @module
        def m2(self):
            pass

        context.consider(conf)

        g = context.create_pgraph()

        solution = solve(g, {g.atom_for(conf):True})

        self.assertIs(True,  solution[g.atom_for(conf)])
        self.assertIs(True,  solution[g.atom_for(m1)])
        self.assertIs(True,  solution[g.atom_for(m2)])

    def test_unused_module(self):
        context = Context()

        @module
        def conf(self):
            self.constrain(m1(isM2 = True))

        @module
        def m1(self, isM2 = False):
            if isM2:
                self.constrain(m2)

        @module
        def m2(self):
            pass

        @module
        def m3(self):
            self.constrain(m4)
            pass

        @module
        def m4(self):
            pass

        context.consider(conf)
        context.consider(m3)
        context.consider(m4)

        g = context.create_pgraph()

        solution = solve(g, {g.atom_for(conf):True})

        self.assertIs(True,  solution[g.atom_for(conf)])
        self.assertIs(True,  solution[g.atom_for(m1)])
        self.assertIs(True,  solution[g.atom_for(m2)])
        self.assertIs(False,  solution[g.atom_for(m3)])
        self.assertIs(False,  solution[g.atom_for(m4)])

    def test_ciclic_dependence(self):
        context = Context()

        @module
        def conf(self):
            self.constrain(m1)

        @module
        def m1(self):
            self.constrain(m2)

        @module
        def m2(self):
            self.constrain(m1)
            pass

        context.consider(conf)

        g = context.create_pgraph()

        solution = solve(g, {g.atom_for(conf):True})

        self.assertIs(True,  solution[g.atom_for(conf)])
        self.assertIs(True,  solution[g.atom_for(m1)])
        self.assertIs(True,  solution[g.atom_for(m2)])


if __name__ == '__main__':
    unittest.main()


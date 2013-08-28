from _compat import *

import unittest

from mybuild.binding.pydsl import module
from mybuild.context import resolve
from mybuild.solver import solve
from mybuild.solver import SolveError


class SolverTestCase(unittest.TestCase):

    def test_simple_solution(self):
        @module
        def conf(self):
            self._constrain(m1(isM2=True))

        @module
        def m1(self, isM2=False):
            if isM2:
                self._constrain(m2)

        @module
        def m2(self):
            pass

        modules = resolve(conf)

        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)

    def test_unused_module(self):
        @module
        def conf(self):
            self._constrain(m1(isM2=True))

        @module
        def m1(self, isM2=False):
            if isM2:
                self._constrain(m2)

        @module
        def m2(self):
            pass

        @module
        def m3(self):
            self._constrain(m4)
            pass

        @module
        def m4(self):
            pass

        modules = resolve(conf)

        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)
        self.assertNotIn(m3, modules)
        self.assertNotIn(m4, modules)

    def test_cyclic_dependence(self):
        @module
        def conf(self):
            self._constrain(m1)

        @module
        def m1(self):
            self._constrain(m2)

        @module
        def m2(self):
            self._constrain(m1)

        modules = resolve(conf)

        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)

    def test_parameter_violation_error(self):
        @module
        def conf(self):
            self._constrain(m1(a=True))
            self._constrain(m1(a=False))

        @module
        def m1(self, a=False):
            pass

        with self.assertRaises(SolveError):
            self.wafctx.my_resolve(conf)

    def test_solve(self):
        #(~A | A&~A)
        @module
        def conf(self):
            self._constrain(m1)

        @module
        def m1(self, a=False):
            if a:
                self._constrain(m2)
            else:
                self._constrain(m3(a=False))

        @module
        def m2(self):
            self._constrain(m3(a=True))
            self._constrain(m3(a=False))

        @module
        def m3(self, a=False):
            pass

        modules = resolve(conf)

        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertNotIn(m2, modules)
        self.assertIn(m3, modules)


def suite(wafctx_):
    class WafCtxBoundTestCase(SolverTestCase):
        wafctx = wafctx_
    return unittest.TestLoader().loadTestsFromTestCase(WafCtxBoundTestCase)

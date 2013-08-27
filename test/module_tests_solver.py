import unittest
from unittest import TestCase

from mybuild.binding.pydsl import module
from mybuild.context import Context
from mybuild.solver import solve
from mybuild.solver import SolveError
import mywaf

class SolverTestCase(TestCase):

    def test_simple_solution(self):
        context = Context()

        @module
        def conf(self):
            self._constrain(m1(isM2 = True))

        @module
        def m1(self, isM2 = False):
            if isM2:
                self._constrain(m2)

        @module
        def m2(self):
            pass

        instances = context.resolve(conf)
        modules = set(map(type, instances))
        
        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)

    def test_unused_module(self):
        context = Context()

        @module
        def conf(self):
            self._constrain(m1(isM2 = True))

        @module
        def m1(self, isM2 = False):
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

        instances = context.resolve(conf)
        modules = set(map(type, instances))
        
        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)
        self.assertNotIn(m3, modules)
        self.assertNotIn(m4, modules)

    def test_cyclic_dependence(self):
        context = Context()

        @module
        def conf(self):
            self._constrain(m1)

        @module
        def m1(self):
            self._constrain(m2)

        @module
        def m2(self):
            self._constrain(m1)

        instances = context.resolve(conf)
        modules = set(map(type, instances))
        
        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertIn(m2, modules)
        
    def test_parameter_violation_error(self):
        context = Context()
        
        @module
        def conf(self):
            self._constrain(m1(a = True))
            self._constrain(m1(a = False))

        @module
        def m1(self, a = False):
            pass
        
        context.consider(conf)
        g = context.create_pgraph()
        
        with self.assertRaises(SolveError):
            mywaf.my_resolve(context, conf)

    def test_solve(self):
        #(~A | A&~A)
        context = Context()
        
        @module
        def conf(self):
            self._constrain(m1)

        @module
        def m1(self, a = False):
            if a:
                self._constrain(m2)
            else:
                self._constrain(m3(a=False))
    
        @module
        def m2(self):
            self._constrain(m3(a=True))
            self._constrain(m3(a=False))
        
        @module
        def m3(self, a = False):
            pass
            
        instances = context.resolve(conf)
        modules = set(map(type, instances))
        
        self.assertIn(conf, modules)
        self.assertIn(m1, modules)
        self.assertNotIn(m2, modules)
        self.assertIn(m3, modules)

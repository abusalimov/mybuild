"""
Tests for Mybuild core.
"""

from contextlib import contextmanager
import unittest
from unittest import TestCase

from mybuild import module
from mybuild.constraints import Constraints
from mybuild.constraints import ConstraintError


class ConstraintsTestCase(TestCase):
    """Tests for Constraints and friends."""

    def setUp(self):
        self.invariants = []

    @contextmanager
    def assertInvariants(self, fxns=None):
        if fxns is None:
            fxns = self.invariants
        fxns = tuple(fxns)

        def iter_eval():
            for fxn in fxns:
                try:
                    res = fxn()
                except Exception as e:
                    res = type(e), e.args
                yield res

        before = tuple(iter_eval())

        try:
            yield

        finally:
            after = tuple(iter_eval())

            self.assertEqual(before, after)

    def test_no_forks(self):
        @module
        def m(self, foo, bar):
            pass

        c = Constraints()

        self.invariants += [
            lambda: c.check(m),
            lambda: c.check(m, 'foo', value=42),
            lambda: c.check(m, 'foo', value=17),

            lambda: c.get(m),
            lambda: c.get(m, 'foo'),
        ]

        assert_error = lambda: self.assertRaises(ConstraintError)
        assert_pure  = lambda: self.assertInvariants()

        # Test a newly created constraints object.

        with assert_pure(), assert_error(): c.get(m)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIs(None, c.check(m))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=17))

        # Test with a single excluded option value.
        c.constrain(m, 'foo', value=17, negated=True)

        with assert_pure(), assert_error(): c.get(m)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIs(None, c.check(m))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(False, c.check(m, 'foo', value=17))

        # Test with a module definitely included.
        c.constrain(m)

        with assert_pure(): self.assertIs(True, c.get(m))
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIs(True, c.check(m))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(False, c.check(m, 'foo', value=17))

        # Test with an exact value for the option.
        c.constrain(m, 'foo', value=42)

        with assert_pure(): self.assertIs(True, c.check(m))
        with assert_pure(): self.assertIs(True, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(False, c.check(m, 'foo', value=17))

    def test_excluded_module(self):
        @module
        def m(self, foo, bar):
            pass

        assert_error = lambda: self.assertRaises(ConstraintError)
        assert_pure  = lambda: self.assertInvariants()

        # Test a newly created constraints object.
        c = Constraints()

        with assert_pure(), assert_error(): c.get(m)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIs(None, c.check(m))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(None, c.check(m, 'foo', value=17))

        # Test with a module definitely excluded.
        c.constrain(m, negated=True)

        with assert_pure(): self.assertIs(False, c.get(m))
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIs(False, c.check(m))
        with assert_pure(): self.assertIs(False, c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIs(False, c.check(m, 'foo', value=17))

        # should die after this
        with assert_pure(), assert_error(): c.constrain(m, 'foo', value=42)

        self.assertFalse(c.is_alive())

    def test_module_without_constrains(self):
        @module
        def m(self):
            pass

        # Test a fresh constraints object.
        c = Constraints()

        c.constrain(m)

        self.assertIs(True, c.check(m))

    def test_identic_modules_with_static_constrains(self):
        @module
        def m(self, foo, bar):
            pass

        # Test a fresh constraints object.
        c = Constraints()

        # Test with an exact value for the option.
        c.constrain(m, 'bar', value=2)

        self.assertIs(True, c.check(m))

        self.assertIs(True, c.check(m, 'bar', value=2))

        c.constrain(m, 'foo', value=42)

    def test_different_modules_with_static_constrains(self):
        @module
        def m1(self, foo, bar):
            pass

        @module
        def m2(self, foo, bar):
            pass

        # Test a fresh constraints object.
        c = Constraints()

        # Test with an exact value for the option.
        c.constrain(m1, 'bar', value=2)

        self.assertIs(True, c.check(m1))
        self.assertIs(True, c.check(m1, 'bar', value=2))
        self.assertIs(None, c.check(m2))

        c.constrain(m2, 'foo', value=42)
        self.assertIs(True, c.check(m2))
        self.assertIs(True, c.check(m2, 'foo', value=42))


if __name__ == '__main__':
    unittest.main()


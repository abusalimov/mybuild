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

    @contextmanager
    def assertLeftsUnchanged(self, fxns):
        def iter_eval():
            for fxn in fxns:
                try:
                    res = fxn()
                except Exception as e:
                    res = type(e)
                else:
                    yield res

        before = tuple(iter_eval())

        try:
            yield
        finally:
            after = tuple(iter_eval())

            for old, new in zip(before, after):
                self.assertEqual(old, new)

    def test_no_forks(self):
        @module
        def m(self, foo, bar):
            pass

        # Test a fresh constraints object.
        c = Constraints()

        invariants = [
            lambda: c.check(m),
            lambda: c.check(m, value=False),
            lambda: c.check(m, 'foo'),
            lambda: c.check(m, 'foo', value=42),
            lambda: c.check(m, 'foo', value=17),

            lambda: c.get(m),
            lambda: c.get(m, 'foo'),
        ]

        assert_error = lambda: self.assertRaises(ConstraintError)
        assert_pure  = lambda: self.assertLeftsUnchanged(invariants)

        with assert_pure(), assert_error(): c.get(m)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIsNone(c.check(m))
        with assert_pure(): self.assertIsNone(c.check(m, 'foo', value=42))
        with assert_pure(): self.assertIsNone(c.check(m, 'foo', value=17))

        # Test with a single excluded option value.
        c.constrain(m, 'foo', value=17, negated=True)

        with assert_pure(), assert_error(): c.constrain(m, 'foo', value=17)
        with assert_pure(), assert_error(): c.get(m)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertIsNone(c.check(m))
        with assert_pure(): self.assertIsNone(c.check(m, 'foo', value=42))
        with assert_pure(): self.assertFalse(c.check(m, 'foo', value=17))

        # Test with a module definitely included.
        c.constrain(m, value=True)

        with assert_pure(): self.assertTrue(c.get(m))
        with assert_pure(), assert_error(): c.constrain(m, value=False)
        with assert_pure(), assert_error(): c.get(m, 'foo')

        with assert_pure(): self.assertTrue(c.check(m))
        with assert_pure(): self.assertIsNone(c.check(m, 'foo', value=42))
        with assert_pure(): self.assertFalse(c.check(m, 'foo', value=17))

        # Test with an exact value for the option.
        c.constrain(m, 'foo', value=42)

        with assert_pure(): self.assertTrue(c.check(m))
        with assert_pure(): self.assertTrue(c.check(m, 'foo', value=42))
        with assert_pure(): self.assertFalse(c.check(m, 'foo', value=17))


if __name__ == '__main__':
    unittest.main()


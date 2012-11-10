"""
Tests for Mybuild core.
"""

import unittest
from unittest import TestCase

from mybuild.core import module
from mybuild.constraints import Constraints
from mybuild.constraints import ConstraintError


class ConstraintsTestCase(TestCase):
    """Tests for Constraints and friends."""

    def test_no_forks(self):
        @module
        def m(self, foo, bar):
            pass

        # Test a fresh constraints object.
        c = Constraints()

        with self.assertRaises(ConstraintError): c.get(m)
        with self.assertRaises(ConstraintError): c.get(m, 'foo')

        self.assertIsNone(c.check(m))
        self.assertIsNone(c.check(m, 'foo', value=42))
        self.assertIsNone(c.check(m, 'foo', value=17))

        # Test with a single excluded option value.
        c.constrain(m, 'foo', value=17, negated=True)

        with self.assertRaises(ConstraintError): c.constrain(m, 'foo', value=17)
        with self.assertRaises(ConstraintError): c.get(m)
        with self.assertRaises(ConstraintError): c.get(m, 'foo')

        self.assertIsNone(c.check(m))
        self.assertIsNone(c.check(m, 'foo', value=42))
        self.assertFalse(c.check(m, 'foo', value=17))

        # Test with a module definitely included.
        c.constrain(m, value=True)

        self.assertTrue(c.get(m))
        with self.assertRaises(ConstraintError): c.constrain(m, value=False)
        with self.assertRaises(ConstraintError): c.get(m, 'foo')

        self.assertTrue(c.check(m))
        self.assertIsNone(c.check(m, 'foo', value=42))
        self.assertFalse(c.check(m, 'foo', value=17))

        # Test with an exact value for the option.
        c.constrain(m, 'foo', value=42)

        self.assertTrue(c.check(m))
        self.assertTrue(c.check(m, 'foo', value=42))
        self.assertFalse(c.check(m, 'foo', value=17))


if __name__ == '__main__':
    unittest.main()


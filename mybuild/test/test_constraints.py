"""
Tests for Mybuild core.
"""

import unittest
from unittest import TestCase

from mybuild.core import module
from mybuild.constraints import Constraints


class ConstraintsTestCase(TestCase):
    """Tests for Constraints and friends."""

    def test_no_forks(self):
        @module
        def m(self, foo, bar):
            pass

        c = Constraints()

        self.assertIsNone(c.check(m))
        self.assertIsNone(c.check(m, 'foo', 42))
        self.assertIsNone(c.check(m, 'foo', 17))

        c.constrain(m, 'foo', 17, negated=True)

        self.assertIsNone(c.check(m))
        self.assertIsNone(c.check(m, 'foo', 42))
        self.assertFalse(c.check(m, 'foo', 17))

        c.constrain(m, 'foo', 42)

        self.assertTrue(c.check(m))
        self.assertTrue(c.check(m, 'foo', 42))
        self.assertFalse(c.check(m, 'foo', 17))


if __name__ == '__main__':
    unittest.main()


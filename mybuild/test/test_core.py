"""
Tests for Mybuild core.
"""

from unittest import TestCase
# from mock import Mock, patch

from mybuild.core import module
from mybuild.core import Constraints


class ModuleTestCase(TestCase):
    """High-level tests for @module deco."""

    def test_without_options(self):
        @module
        def m(self):
            pass
        self.assertEqual(tuple(m._options), ())

    def test_with_options(self):
        @module
        def m(self, foo, bar):
            pass
        self.assertEqual(tuple(m._options), ('foo', 'bar'))

    def test_func_with_starargs(self):
        """Module function must not declare neither *args nor **kwargs."""

        with self.assertRaises(TypeError):
            @module
            def m(self, *args):
                pass

        with self.assertRaises(TypeError):
            @module
            def m(self, **kwargs):
                pass

    def test_options_with_leading_underscore(self):
        """Module options must not start with an underscore."""

        with self.assertRaises(TypeError):
            @module
            def m(self, _foo):
                pass

class ConstraintsTestCase(TestCase):
    """Tests for Constraints and friends."""

    def test_xxx(self):
        pass

if __name__ == '__main__':
    unittest.main()


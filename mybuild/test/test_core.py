"""
Tests for Mybuild core.
"""

import unittest

from mybuild.core import module

class ModuleTestCase(unittest.TestCase):

    def test_def_module_without_options(self):
        @module
        def m(self):
            pass
        self.assertEqual(tuple(m._options), ())

    def test_def_module_with_options(self):
        @module
        def m(self, foo, bar):
            pass
        self.assertEqual(tuple(m._options), ('foo', 'bar'))

    def test_def_module_func_with_starargs(self):
        """Module function must not declare neither *args nor **kwargs."""

        with self.assertRaises(TypeError):
            @module
            def m(self, *args):
                pass

        with self.assertRaises(TypeError):
            @module
            def m(self, **kwargs):
                pass

    def test_def_module_options_with_leading_underscore(self):
        """Module options must not start with an underscore."""

        with self.assertRaises(TypeError):
            @module
            def m(self, _foo):
                pass


if __name__ == '__main__':
    unittest.main()


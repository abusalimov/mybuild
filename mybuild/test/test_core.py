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

    def test_def_invalid_module_options(self):
        with self.assertRaises(TypeError):
            @module
            def m(self, foo, *args):
                pass


if __name__ == '__main__':
    unittest.main()


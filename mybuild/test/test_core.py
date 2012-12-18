"""
Tests for Mybuild core.
"""

import unittest
from unittest import TestCase
# from mock import Mock, patch

from mybuild import module


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
        self.assertEqual(tuple(m._options._fields), ('foo', 'bar'))

    def test_func_with_starargs(self):
        """Module function must not declare neither *args nor **kwargs."""

        with self.assertRaises(TypeError):
            @module
            def m1(self, *args):
                pass

        with self.assertRaises(TypeError):
            @module
            def m2(self, **kwargs):
                pass

    def test_options_with_leading_underscore(self):
        """Module options must not start with an underscore."""

        with self.assertRaises(TypeError):
            @module
            def m(self, _foo):
                pass


###############################################################################

if __name__ == '__main__':

    import mybuild.logs as log


    log.zones = {'mybuild'}
    log.verbose = True
    log.init_log()


    @module
    def conf(mod):
        mod.constrain(m0(o=42))

    @module
    def m0(mod, o):
        mod1 = mod.ask(m1)
        t = "with m1" if mod1 else "no m1"
        log.debug("mybuild: <m0> o=%s, %s, m1.x=%r" % (o, t, mod1.x))

    @module
    def m1(mod, x=11):
        mod0 = mod.ask(m0)
        if mod0.o < 43:
            mod._context.consider(m0, "o", mod0.o + 1)
        log.debug("mybuild: <m1> x=%s, m0.o=%d" % (x, mod0.o))



    # build(conf)

    unittest.main()


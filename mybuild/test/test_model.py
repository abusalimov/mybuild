'''
Created on Nov 13, 2012

@author: Anton Bondarev
'''
import unittest
from unittest import TestCase

from mybuild import module

from mybuild.constraints import Constraints

from mybuild import option

class ModelTestCase(TestCase):
    def test_without_options(self):
        c = Constraints()
        
        @module
        def m(self):
            pass
        
        @module
        def conf(self):
            self.constrain(m())
        
        c.constrain(conf)
        
        #self.assertTrue(c.is_resolved())
        
    def test_with_default_options(self):
        c = Constraints()
        
        @module
        def m(self,
              foo = option.bool(default=True),
              ):
            pass
        
        @module
        def conf(self):
            self.constrain(m())
        
        c.constrain(conf)
        
        #self.assertTrue(c.is_resolved())
    
    def test_with_dependences(self):
        c = Constraints()
        
        @module
        def m(self,
              foo = option(0, 'one', 'two'),    # one of these, or any other
              bar = option.enum(38400, 115200), # enumeration of two values
              baz = option.bool(default=True),  # boolean flag
              ):
            pass
        
        @module
        def m1(self, foo):
            pass
        
        @module
        def conf(self):
            self.constrain(m(foo='one', bar=38400, baz=True))
            self.constrain(m1(foo='three'))
        
        c.constrain(conf)
        #self.assertTrue(c.is_resolved())
   

if __name__ == '__main__':
    unittest.main()

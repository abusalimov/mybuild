import unittest
from unittest import TestCase

from mybuild.solver import *

class PdagDtreeTestCase(TestCase):

    def test_01(self):
        from mybuild import module
        from mybuild.context import Context
        
        context = Context()
        
        @module
        def conf(self):
            self.constrain(m1(isM2 = True))

        @module
        def m1(self, isM2 = False):
            if isM2:
                self.constrain(m2)
        
        @module
        def m2(self):
            pass

        context.consider(conf)

        g = context.create_pgraph()

        solution = solve(g, {g.atom_for(conf):True})
       
        self.assertIs(True,  solution[g.atom_for(conf)]) 
        self.assertIs(True,  solution[g.atom_for(m1)]) 
        self.assertIs(True,  solution[g.atom_for(m2)]) 
        
if __name__ == '__main__':
    import mybuild.logs as log

    log.init_log()
    unittest.main()
    
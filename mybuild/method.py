
import types

from mybuild.mybuild.context import Context

from mybuild.mybuild import module
from dtree import Dtree

def method_pre_parse(ctx):
    ctx.root = types.ModuleType('root')
    ctx.constr = []
    ctx.runlevels = {}
    return ctx

def method_decide_build(ctx):
    @module
    def conf(self):
        print ctx.constr
        for name, constr in ctx.constr:
            obj = ctx.root
            for i in name.split('.'):
                obj = getattr(obj, i)

            print obj
            self.constrain(obj(**constr))

    context = Context()
    context.consider(conf)

    conf_atom = context.atom_for(conf)
    pdag, constraint = context.create_pdag_with_constraint()
    dtree = Dtree(pdag)
    solution = dtree.solve({constraint:True, conf_atom:True})

    from pprint import pprint
    pprint(solution)

    return solution 

def method_define_build(bld, model) :
    pass


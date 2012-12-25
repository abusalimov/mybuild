
import types

from mybuild.mybuild.context import Context, InstanceAtom

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
        for name, constr in ctx.constr:
            obj = ctx.root
            for i in name.split('.'):
                obj = getattr(obj, i)

            self.constrain(obj(**constr))

    context = Context()
    context.consider(conf)

    g = context.create_pdag()

    dtree = Dtree(g)
    solution = dtree.solve({g.atom_for(conf):True})

    return solution 

def method_define_build(ctx):
    for pnode, value in ctx.model.iteritems():
        if isinstance(pnode, InstanceAtom):
            srcs = getattr(pnode.instance, 'sources', '')
            print srcs
            #pnode.build(ctx)



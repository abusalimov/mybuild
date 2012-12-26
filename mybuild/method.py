
from mybuild.mybuild.context import Context, InstanceAtom

from mybuild.mybuild import module
from dtree import Dtree

from mybuild.package import Package

import mybuild.mybuild.logs as log

def method_pre_parse(ctx):
    ctx.root = Package('root')
    ctx.constr = []
    ctx.runlevels = {}
    return ctx

def method_decide_build(ctx):
    print ctx.constr
    @module
    def conf(self):
        self.qualified_name = 'conf'
        for name, constr in ctx.constr:
            print name
            obj = ctx.root
            for i in name.split('.'):
                obj = getattr(obj, i)

            print obj, constr
            self.constrain(obj(**constr))

    log.zones = set([
                    'dtree',
                    'pdag',
                    'mybuild',
                    ])
    log.verbose = True
    log.init_log()

    context = Context()
    context.consider(conf)

    g = context.create_pdag()

    dtree = Dtree(g)
    solution = dtree.solve({g.atom_for(conf):True})

    return solution 

def method_define_build(ctx):
    for pnode, value in ctx.model.iteritems():
        if isinstance(pnode, InstanceAtom):
            pnode.build(ctx)



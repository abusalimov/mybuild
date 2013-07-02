from mybuild import mywaf
from mybuild.context import Context, InstanceAtom
from mybuild.solver import solve

from mybuild.compat import *


def create_model(bld):
    def get_defaults():
        from mybuild import module, option
        return locals()

    prj = bld.my_load('prj', ['src', bld.env.TEMPLATE], get_defaults(), ['Pybuild'])

    ################################
    conf = prj.conf.conf

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    for pnode, value in iteritems(solution):
        if isinstance(pnode, InstanceAtom):
            print '>>>', value, pnode
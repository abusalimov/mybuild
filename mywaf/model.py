import os

import mybuild
from mybuild import loader
from mybuild.context import Context, InstanceAtom
from mybuild.solver import solve

from mybuild.util.compat import *


from waflib.Task import Task
from waflib.TaskGen import feature, extension, after_method
from waflib.Tools import ccroot


def build_true_graph(bld, solution):
    bld.my_recurse(pnode.instance for pnode, value in iteritems(solution)
                   if value and isinstance(pnode, InstanceAtom))


def create_model(bld):
    def get_defaults():
        from mybuild import module, option
        return locals()

    defaults = get_defaults()

    def create_module(pymodule_name, dictionary):
        print dictionary
        def module_func(self):
            for key, value in dictionary:
                setattr(self, key, value)
        module_func.__module__ = pymodule_name
        module_func.__name__ = dictionary.pop('id')
        return mybuild.module(module_func)

    defaults['!module'] = create_module

    prj = bld.my_load('prj', ['src', bld.env.TEMPLATE], defaults, ['Pybuild'])

    print '>>>>>>>>', prj.hello.yaml_module

    ################################
    conf = prj.conf.PYBUILD.conf

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    true_g = build_true_graph(bld, solution)




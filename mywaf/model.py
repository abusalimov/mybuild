import os


from waflib.Task import Task
from waflib.TaskGen import feature, extension, after_method
from waflib.Tools import ccroot

import mybuild
from nsloader.yamlfile import YamlFileLoader
from mybuild.dsl.myfile import MybuildMyFileLoader
from mybuild.dsl.pyfile import MybuildPyFileLoader

from mybuild.context import Context, InstanceAtom
from mybuild.solver import solve

from util.compat import *


def build_true_graph(bld, solution):
    bld.my_recurse(pnode.instance for pnode, value in iteritems(solution)
                   if value and isinstance(pnode, InstanceAtom))


def create_model(bld):
    def create_module(pymodule_name, dictionary):
        def module_func(self):
            for key, value in dictionary:
                setattr(self, key, value)
        module_func.__module__ = pymodule_name
        module_func.__name__ = dictionary.pop('id')
        return mybuild.dsl.pyfile.module(module_func)

    loaders_init = {
        MybuildMyFileLoader: None,
        MybuildPyFileLoader: None,
        YamlFileLoader: {'!module': create_module},
    }

    try:
        prj = bld.my_load('prj', ['src', bld.env.TEMPLATE], loaders_init)

    except:
        raise

        import sys, traceback, code
        tb = sys.exc_info()[2]
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)


    print '>>>>>>>>', prj.hello.yaml_module

    ################################
    conf = prj.conf.conf

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    true_g = build_true_graph(bld, solution)




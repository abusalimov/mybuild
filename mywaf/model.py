import os


from waflib.Task import Task
from waflib.TaskGen import feature, extension, after_method
from waflib.Tools import ccroot

import mybuild
from mybuild.dsl.myloader import MybuildFileLoader
from nsloader.yamlfile import YamlFileLoader
from nsloader.pyfile import PyFileLoader
# from mybuild.dsl.myloader import MybuildFileLoader
# from mybuild.dsl.my_yaml import YamlFileLoader
# from mybuild.dsl.pybuild import PyFileLoader

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
        return mybuild.pybinding.module(module_func)

    def get_pybuild_defaults():
        from mybuild.pybinding import module, option
        return locals()

    def get_mybuild_defaults():
        class fake(object):
            def __init__(self, *args, **kwargs):
                super(fake, self).__init__()
                print args, kwargs

        class module(fake):
            pass
        from mybuild.pybinding import option
        return locals()

    loaders_init = {
        MybuildFileLoader: get_mybuild_defaults(),
        YamlFileLoader: {'!module': create_module},
        PyFileLoader: get_pybuild_defaults(),
    }

    prj = bld.my_load('prj', ['src', bld.env.TEMPLATE], loaders_init)

    print '>>>>>>>>', prj.hello.yaml_module

    ################################
    conf = prj.conf.conf

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    true_g = build_true_graph(bld, solution)




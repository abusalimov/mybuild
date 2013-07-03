import os

from mybuild import loader
from mybuild.context import Context, InstanceAtom
from mybuild.solver import solve

from mybuild.util.compat import *


from waflib.Task import Task
from waflib.TaskGen import feature, extension, after_method
from waflib.Tools import ccroot


def add_mytask(bld, pnode):
    mod = pnode.instance.module
    fullfile = mod._file
    fnode = bld.root.find_node(fullfile)

    bld.pre_recurse(fnode)
    folder = fnode.parent
    src = getattr(pnode.instance, 'sources', [])
    bld(features='mylink', source=src, target='test')
    print('+++++++++ add task ++++')
    print('module = ' + str(mod))
    print('folder = ' + folder.abspath())
    print('sources = ' + str(src))
    bld.post_recurse(fnode)
    print('+++++++++++++++++++++++')


def build_true_graph(bld, solution):
    ret = dict()
    for pnode, value in iteritems(solution):
        if isinstance(pnode, InstanceAtom):
            if str(pnode) != 'prj.conf.conf()':
                if value == True:
                    add_mytask(bld, pnode)

    return ret


def create_model(bld):
    def get_defaults():
        from mybuild import module, option
        return locals()

    prj = bld.my_load('prj', ['src', bld.env.TEMPLATE], get_defaults(), ['Pybuild'])

    ################################
    conf = prj.conf.PYBUILD.conf

    context = Context()
    context.consider(conf)

    g = context.create_pgraph()

    solution = solve(g, {g.atom_for(conf):True})

    true_g = build_true_graph(bld, solution)



@after_method('process_source')
@feature('mylink')
def call_apply_link(self):
    print('link')
    print(self)

@extension('.c')
def process_ext(self, node):
    #self.create_compiled_task('ext2o', node)
    print(node)

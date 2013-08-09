"""
Mybuild tool for Waf.
"""

import os.path

from operator import attrgetter

from waflib import Context as wafcontext
from waflib import Utils   as wafutils
from waflib import Errors  as waferrors

from mybuild.context import resolve

from glue import PyDslLoader
from glue import MyDslLoader

from nsimporter import import_all
from nsimporter import loader_filename

from util.misc import is_mapping
from util.operator import instanceof
from util.compat import *


def init(ctx):
    print('mywaf: init %r' % ctx)

def options(ctx):
    print('mywaf: options %r' % ctx)

def configure(ctx):
    print('mywaf: configure %r' % ctx)


DEFAULT_LOADERS = [MyDslLoader, PyDslLoader]

def my_load(ctx, namespace, path=None, loaders=DEFAULT_LOADERS):
    loaders_init = (dict if is_mapping(loaders) else dict.fromkeys)(loaders)

    if path is not None:
        path = wafutils.to_list(path)
        path_nodes = [ctx.path.find_node(entry) for entry in path]
    else:
        path_nodes = [ctx.path]
    path = [node.abspath() for node in path_nodes]

    loader_files_glob = ['**/' + loader_filename(l) for l in loaders_init]
    found_rel_dirs = sorted(set(found.parent.path_from(node)
                             for node in path_nodes
                             for found in node.ant_glob(loader_files_glob)))

    def no_dots(dirname):
        has_dot = ('.' in dirname)
        if has_dot:
            if dirname != '.':
                Logs.warn("A dot in '{dirname}' path, skipping"
                          .format(**locals()))
        return not has_dot

    return import_all(filter(no_dots, found_rel_dirs), namespace, path,
                      loaders_init)

wafcontext.Context.my_load = my_load


def my_recurse(ctx, instances, name=None, mandatory=True, once=True):
    if name is None:
        name = ctx.fun

    for instance in instances:
        node = ctx.root.find_node(instance._file)

        ctx.pre_recurse(node)
        try:
            user_function = getattr(instance, name, None)
            if not user_function:
                if not mandatory:
                    continue
                raise waferrors.WafError('No method %s defined in %s' %
                                         (name, instance))
            user_function(ctx)

        finally:
            ctx.post_recurse(node)

wafcontext.Context.my_recurse = my_recurse


def mybuild(ctx, conf_name, path=None, loaders=DEFAULT_LOADERS):
    namespace, _, conf_relname = conf_name.partition('.')
    if not conf_relname:
        raise ValueError("conf_name must be a qualified name "
                         "(including a namespace): '%s'" % conf_name)
    else:
        conf_getter = attrgetter(conf_relname)

    ns_pymodule = ctx.my_load(namespace, path, loaders)
    conf_module = conf_getter(ns_pymodule)

    try:
        conf_instance, instances = ctx._my_cache[conf_module]
    except KeyError:
        instances = resolve(conf_module, module_mixin=MyWafModuleMixin)
        conf_instance = next(filter(instanceof(conf_module), instances))
        ctx._my_cache[conf_module] = conf_instance, instances

    ctx.my_recurse(instances)

    return conf_instance

wafcontext.Context.mybuild = mybuild
wafcontext.Context._my_cache = {}  # {conf_module: instances}


class MyWafModuleMixin(object):
    """docstring for MyWafModuleMixin"""

    def __init__(self, *args, **kwargs):
        super(MyWafModuleMixin, self).__init__(*args, **kwargs)
        self.sources = []

    def build(self, bld):
        print('mywaf build: %r' % self)
        print('\tsources: %r' % self.sources)
        # bld(features='mylink', source=src, target='test')

    def configure(self, ctx):
        print('mywaf configure: %r' % self)

# try:
#     from waflib.Task import Task
#     from waflib.TaskGen import feature, extension, after_method
#     from waflib.Tools import ccroot

#     @after_method('process_source')
#     @feature('mylink')
#     def call_apply_link(self):
#         print('linking' + str(self))

#     class mylink(ccroot.link_task):
#         run_str = 'cat ${SRC} > ${TGT}'

#     class ext2o(Task):
#         run_str = 'cp ${SRC} ${TGT}'

#     @extension('.c')
#     def process_ext(self, node):
#         self.create_compiled_task('ext2o', node)

# except ImportError:
#     pass  # XXX move Waf-related stuff from here



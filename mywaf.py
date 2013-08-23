"""
Mybuild tool for Waf.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-02"

__all__ = ["MyWafModuleMixin"]  # the rest is bound as Waf Context methods.


from _compat import *

import functools
from operator import attrgetter

from glue import PyDslLoader
from glue import MyDslLoader

from nsimporter import import_all
from nsimporter import loader_filename

from mybuild.context import resolve
from mybuild.solver import SolveError
from mybuild.rgraph import *

from util.collections import is_mapping
from util.deco import defer_call

from collections import deque

from waflib import Context as wafcontext
from waflib import Utils   as wafutils
from waflib import Errors  as waferrors


def wafcontext_method(func):
    setattr(wafcontext.Context, func.__name__, func)
    return func


DEFAULT_LOADERS = [MyDslLoader, PyDslLoader]

@wafcontext_method
def mybuild(ctx, conf_name,
            path=None, loaders=DEFAULT_LOADERS,
            recurse_name=None):
    """Facade function for the whole Mybuild machinery.

    Loads all Mybuild files found in path using given loaders, resolves
    a configuration specified by conf_name and recurses into each enabled
    module.

    Args:
        conf_name (str): a fully qualified name of the configuration including
            a namespace, e.g. 'ns.path.to.conf'.
        path (list/str): a list of strings (or a string of space-separated
            entries) denoting directories to search for Mybuild files.
            If not specified, ctx.path is used instead.
        loaders (iterable/mapping): a list of loaders used to recognize and
            load Mybuild files, or a dictionary mapping such loaders to
            their initializing values (loader-specific).
        recurse_name (str):
            Name of method to invoke on each resolved module. Defaults to
            the name of current context.

    Returns:
        The namespace root wrapped by a module instance accessor
        (see MybuildInstanceAccessor).
    """
    namespace, _, conf_relname = conf_name.partition('.')
    if not conf_relname:
        raise ValueError("conf_name must be a qualified name "
                         "(including a namespace): '%s'" % conf_name)
    else:
        conf_getter = attrgetter(conf_relname)

    ns_pymodule = ctx.my_load(namespace, path, loaders)
    instance_map = ctx.my_resolve(conf_getter(ns_pymodule))
    ctx.my_recurse(sorted(itervalues(instance_map), key=str))

    return MybuildInstanceAccessor(ns_pymodule, instance_map)


@wafcontext_method
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


@wafcontext_method
def my_resolve(ctx, conf_module):
    cache = ctx._my_resolve_cache
    try:
        instance_map = cache[conf_module]
    except KeyError:
        try:
            instances = resolve(conf_module, module_meta=mywaf_module_meta)
        except SolveError as e:
            e.rgraph = get_error_rgraph(e)
            #TODO test it
            #print_graph(e.rgraph)
            raise e
        
        instance_map = dict((instance._module, instance)
                            for instance in instances)
        cache[conf_module] = instance_map

    return instance_map

wafcontext.Context._my_resolve_cache = {}  # {conf_module: instance_map}

def print_graph(rgraph):
    """
    Simple way to print reason graph. Nodes of more one reason are printed 
    in new line without offset.
    """
    node_deque = deque()
    used = set()
        
    def dfs(node, reason, depth):
        if node in used:
            print_reason(reason,depth)
            return
        
        used.add(node)
        print_reason(reason,depth)
        for cons in node.therefore:
            dfs(cons, node.therefore[cons], depth + 1)
            for container in cons.containers:
                process_container(container)
                            
    def process_container(container):
        if container in used:
            return
        used.add(container)
        for ccons in container.therefore:
            if ccons not in node_deque:
                node_deque.appendleft((ccons, container.therefore[ccons]))
                            
    def print_reason(reason, depth):
        print '  ' * depth, reason
        if not reason.follow:
            return
            
        literal = None 
        if reason.literal is not None:
            literal = ~reason.literal
        else:
            literal = reason.cause_literals[0]
        
        assert literal in rgraph.violation_graphs
                
        print '---dead branch {0}---------'.format(literal)
        print_graph(rgraph.violation_graphs[literal])    
        print '---------dead branch {0}---'.format(literal)        
        
    #node_deque contains touples (node, reason)
    for node in rgraph.initial.therefore:
        node_deque.append((node, rgraph.initial.therefore[node]))
        process_container(node)
        
    while node_deque:
        node, reason = node_deque.pop()        
        dfs(node, reason, 0)

@wafcontext_method
def my_recurse(ctx, instances, name=None, mandatory=True):
    if name is None:
        name = ctx.fun

    for instance in instances:
        node = ctx.root.find_node(instance._file)

        ctx.pre_recurse(node)
        try:
            user_function = getattr(instance, name, None)
            if user_function is None:
                if not mandatory:
                    continue
                raise waferrors.WafError('No method %s defined in %s' %
                                         (name, instance))
            user_function(ctx)

        finally:
            ctx.post_recurse(node)


class MybuildInstanceAccessor(object):
    """Proxy class that mimics an underlying object in attribute and item
    access and maps the return value using an internal mapping
    or wraps it with another proxy."""

    __slots__ = ('_{0}__obj _{0}__retmap'
                 .format('MybuildInstanceAccessor').split())

    def __init__(self, obj, retmap):
        super(MybuildInstanceAccessor, self).__init__()
        self.__obj = obj
        self.__retmap = retmap

    def __getattr__(self, attr):
        return self.__get(getattr(self.__obj, attr))
    def __getitem__(self, item):
        return self.__get(self.__obj[item])

    def __get(self, retobj):
        retmap = self.__retmap
        try:
            return retmap[retobj]
        except KeyError:
            cls = type(self)
            return cls(retobj, retmap)


def mywaf_module_meta(name, bases, attrs, **kwargs):
    return new_type(name, bases + (MyWafModuleMixin,), attrs, **kwargs)


class MyWafModuleMixin(object):
    """docstring for MyWafModuleMixin"""

    @defer_call
    def load(ctx, *args, **kwargs):
        ctx.load(*args, **kwargs)

    @defer_call
    def bld(ctx, *args, **kwargs):
        ctx(*args, **kwargs)

    def options(self, ctx):
        print('mywaf options: %r' % self)
        self.load.call_on(ctx)

    def configure(self, ctx):
        print('mywaf configure: %r' % self)
        self.load.call_on(ctx)

    def build(self, bld):
        print('mywaf build: %r' % self)
        self.bld.call_on(bld)


def init(ctx):
    print('mywaf: init %r' % ctx)

def options(ctx):
    print('mywaf: options %r' % ctx)

def configure(ctx):
    print('mywaf: configure %r' % ctx)


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



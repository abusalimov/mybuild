"""
Mybuild tool for Waf.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-02"

__all__ = ["MyWafModuleMixin"]  # the rest is bound as Waf Context methods.


from _compat import *

import functools
import os.path
from operator import attrgetter

from glue import PyDslLoader
from glue import MyDslLoader

from nsimporter import NamespaceImporter

from mybuild.context import resolve
from mybuild.solver import SolveError
from mybuild.rgraph import *

from util.collections import is_mapping
from util.deco import defer_call

from collections import deque

from waflib import Context as wafcontext
from waflib import Errors  as waferrors
from waflib import Node    as wafnode
from waflib import Utils   as wafutils


def ctx_method(func):
    setattr(wafcontext.Context, func.__name__, func)
    return func
wafcontext.ctx_method = ctx_method


NAMESPACE_LOADERS = {
    'Mybuild': MyDslLoader,
    'Pybuild': PyDslLoader,
}

def register_namespace(namespace, path=None, loaders=NAMESPACE_LOADERS):
    """Loads all Mybuild files found in path using given loaders into the
    specified namespace.

    Args:
        namespace (str)
        path (list/str): a list of strings (or a string of space-separated
            entries) denoting directories to search for Mybuild files.
        loaders (mapping): a name-to-loader_type mapping used to recognize and
            load Mybuild files.

    Returns:
        The namespace root module.
    """

    if path is not None:
        path = [os.path.normpath(os.path.join(wafcontext.run_dir, path_entry))
                for path_entry in wafutils.to_list(path)]
    else:
        path = [wafcontext.run_dir]

    return NamespaceImporter(namespace, path, loaders).register()


@wafcontext.ctx_method
def mybuild(ctx, conf_module, recurse_name=None):
    """Facade function for the whole Mybuild machinery.

    Resolves a configuration specified by conf_module and recurses into each
    enabled module.

    Args:
        conf_module (mybuild.core.Module): the configuration to resolve.
        recurse_name (str): Name of method to invoke on each resolved module.
            Defaults to the name of current context.

    Returns:
        The namespace root wrapped by a module instance accessor
        (see MybuildInstanceAccessor).
    """
    instances = ctx.my_resolve(conf_module)
    return ctx.my_recurse(sorted(instances, key=str))


@wafcontext.ctx_method
def my_resolve(ctx, conf_module):
    cache = ctx._my_resolve_cache
    try:
        instances = cache[conf_module]
    except KeyError:
        try:
            instances = resolve(conf_module)
        except SolveError as e:
            e.rgraph = get_error_rgraph(e)
            print_graph(e.rgraph)
            raise e

        cache[conf_module] = instances

    return instances

wafcontext.Context._my_resolve_cache = {}  # {conf_module: instances}


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


@wafcontext.ctx_method
def my_recurse(ctx, instances, name=None, mandatory=False):
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



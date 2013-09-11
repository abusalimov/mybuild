"""
Mybuild tool for Waf.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-02"

__all__ = [
    "namespace_importer",
    "register_namespace",
    "unregister_namespace",
    "mybuild_project",
]  # the rest is bound as Waf Context methods.


from _compat import *

import sys
import os.path

import functools

from glue import PyDslLoader
from glue import MyDslLoader

from nsimporter.hook import NamespaceImportHook

from mybuild.context import resolve
from mybuild.solver import SolveError
from mybuild.rgraph import *

from waflib import Context as wafcontext
from waflib import Errors  as waferrors
from waflib import Logs    as waflogs
from waflib import Utils   as wafutils

import unittest
from test import module_tests_solver
from mybuild.test import test_solver


namespace_importer = NamespaceImportHook(loaders={
    'Mybuild': MyDslLoader,
    'Pybuild': PyDslLoader,
})
sys.meta_path.insert(0, namespace_importer)


def register_namespace(namespace, path='.'):
    """Registers a new namespace recognized by a namespace importer.

    Args:
        namespace (str): namespace root name.
        path (list/str): a list of strings (or a string of space-separated
            entries) denoting directories to search when loading files.
    """

    if '.' in namespace:
        raise NotImplementedError('To keep things simple')

    # normalize path
    path = [os.path.normpath(os.path.join(wafcontext.run_dir, path_entry))
            for path_entry in wafutils.to_list(path)]

    namespace_importer.namespace_path[namespace] = path


def unregister_namespace(namespace):
    """Unregisters and returns a previously registered namespace (if any)."""
    return namespace_importer.namespace_path.pop(namespace, None)


def mybuild_project(module):
    def decorator(func):
        @functools.wraps(func)
        def decorated(ctx):
            ctx.mybuild(module)
            return func(ctx)
        return decorated
    return decorator


def ctx_method(func):
    setattr(wafcontext.Context, func.__name__, func)
    return func
wafcontext.ctx_method = ctx_method


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
    instance_map = ctx.my_resolve(conf_module)
    return ctx.my_recurse(sorted(itervalues(instance_map), key=str))


@wafcontext.ctx_method
def my_resolve(ctx, conf_module):
    cache = ctx._my_resolve_cache
    try:
        instance_map = cache[conf_module]
    except KeyError:
        try:
            instance_map = resolve(conf_module)
        except SolveError as e:
            e.rgraph = get_error_rgraph(e)
            reason_generator = traversal(e.rgraph)
            for reason, depth in reason_generator:
                print_reason(e.rgraph, reason, depth)
            raise e

        cache[conf_module] = instance_map

    return instance_map

wafcontext.Context._my_resolve_cache = {}  # {conf_module: instance_map}


def print_reason(rgraph, reason, depth):
        print ('  ' * depth, reason)
        if not reason.follow:
            return
  
        literal = None
        if reason.literal is not None:
            literal = ~reason.literal
        else:
            literal = reason.cause_literals[0]
  
        assert literal in rgraph.violation_graphs
  
        print('---dead branch {0}---------'.format(literal))
        reason_generator = traversal(rgraph.violation_graphs[literal])
        for reason in reason_generator:
            print_reason(rgraph, reason[0], reason[1])   
        print('---------dead branch {0}---'.format(literal))


@wafcontext.ctx_method
def my_recurse(ctx, instances, name=None, mandatory=True):
    if name is None:
        name = ctx.fun

    for instance in instances:
        node = ctx.root.find_node(instance._file)

        ctx.pre_recurse(node)
        for tool in instance.tools:
            try:
                user_function = getattr(tool, name, None)
                if user_function is None:
                    if not mandatory:
                        continue
                    msg = ("No method '{name}' defined in {tool} "
                           "needed for {instance}".format(**locals()))
                    raise waferrors.WafError(msg)
                user_function(instance, ctx)

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

def selftest(ctx):
    suite = unittest.TestSuite()
    suite.addTests([
        test_solver.suite(),
        module_tests_solver.suite(ctx),
    ])

    unittest.TextTestRunner(verbosity=waflogs.verbose).run(suite)


# from waflib.Task import Task
# from waflib.TaskGen import feature, extension, after_method
# from waflib.Tools import ccroot

# @after_method('process_source')
# @feature('mylink')
# def call_apply_link(self):
#     print('linking' + str(self))

# class mylink(ccroot.link_task):
#     run_str = 'cat ${SRC} > ${TGT}'

# class ext2o(Task):
#     run_str = 'cp ${SRC} ${TGT}'

# @extension('.c')
# def process_ext(self, node):
#     self.create_compiled_task('ext2o', node)



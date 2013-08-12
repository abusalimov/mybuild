"""
Mybuild tool for Waf.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-02"

__all__ = ["MyWafModuleMixin"]  # the rest is bound as Waf Context methods.


from _compat import *

from operator import attrgetter

from glue import PyDslLoader
from glue import MyDslLoader

from nsimporter import import_all
from nsimporter import loader_filename

from mybuild.context import resolve

from util.misc import is_mapping

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
        instances = resolve(conf_module, module_mixin=MyWafModuleMixin)
        instance_map = dict((instance._module, instance)
                            for instance in instances)
        cache[conf_module] = instance_map

    return instance_map

wafcontext.Context._my_resolve_cache = {}  # {conf_module: instance_map}


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


class MyWafModuleMixin(object):
    """docstring for MyWafModuleMixin"""

    def __init__(self, *args, **kwargs):
        super(MyWafModuleMixin, self).__init__(*args, **kwargs)
        self._bld_calls = []  # list of (args, kwargs) tuples

    def bld(self, *args, **kwargs):
        self._bld_calls.append((args, kwargs))

    def build(self, bld):
        print('mywaf build: %r' % self)

        for args, kwargs in self._bld_calls:
            bld(*args, **kwargs)

    def configure(self, ctx):
        print('mywaf configure: %r' % self)


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



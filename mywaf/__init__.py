"""
Mybuild tool for Waf.
"""

import os.path

from waflib import Context as wafcontext
from waflib import Utils   as wafutils
from waflib import Errors  as waferrors

from mybuild.loader import import_all
from mybuild.loader import loader_filenames

from util.collections import OrderedDict
from util.compat import *

def options(ctx):
    print('mywaf: %r' % ctx)

def configure(ctx):
    print('mywaf: %r' % ctx)


def my_load(ctx, namespace, path=None, loaders_init=None):
    myfile_names = list(itervalues(loader_filenames(loaders_init)))
    myfiles_glob = ['**/' + f for f in myfile_names]

    if path is not None:
        path_nodes = [ctx.path.find_node(entry) for entry in path]
    else:
        path_nodes = [ctx.path]

    path = [node.abspath() for node in path_nodes]

    found_names = sorted(set(found.parent.path_from(node)
                             for node in path_nodes
                             for found in node.ant_glob(myfiles_glob)))

    def no_dots(dirname):
        has_dot = ('.' in dirname)
        if has_dot:
            if dirname != '.':
                Logs.warn("A dot in '{dirname}' path, skipping"
                          .format(**locals()))
        return not has_dot

    return import_all(filter(no_dots, found_names), namespace, path,
                      loaders_init)

wafcontext.Context.my_load = my_load


def my_recurse(ctx, instances, name=None, mandatory=True, once=True):
    if name is None:
        name = ctx.fun

    for instance in instances:
        node = ctx.root.find_node(instance.module._file)

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

"""
Mybuild tool for Waf.
"""

import os.path

from waflib import Context as wafcontext
from waflib import Utils   as wafutils

from mybuild.loader import mybuild_importer
from mybuild.util.collections import OrderedDict

from mybuild.util.compat import *

def options(ctx):
    print('mywaf: %r' % ctx)

def configure(ctx):
    print('mywaf: %r' % ctx)

def my_load(ctx, namespace, path=None, defaults=None,
            myfile_names=['Pybuild']):

    myfile_names = wafutils.to_list(myfile_names)
    myfiles_glob = ['**/' + f for f in myfile_names]

    if path is not None:
        path_nodes = [ctx.path.find_node(entry) for entry in path]
    else:
        path_nodes = [ctx.path]

    path = [node.abspath() for node in path_nodes]

    found_names = sorted(set(found.parent.path_from(node)
                             for node in path_nodes
                             for found in node.ant_glob(myfiles_glob)))

    with mybuild_importer.using_namespace(namespace, path, defaults):
        for dirname in found_names:
            if '.' in dirname:
                if dirname != '.':
                    Logs.warn("A dot in '{dirname}' path, skipping"
                              .format(**locals()))
                continue

            package = namespace + '.' + dirname.replace(os.path.sep, '.')
            try:
                __import__(package)
            except ImportError as e:
                raise
                ctx.fatal('Unable to import {package} found in {dirname}'
                          .format(**locals()), e)

    return __import__(namespace)

wafcontext.Context.my_load = my_load

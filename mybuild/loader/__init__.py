"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-06-26"

__all__ = [
    "mybuild_importer",

    "import_all",
    "normalize_loaders",
    "loader_filenames",
]


import contextlib
import functools
import sys
import os.path

from .package import NamespacePackageLoader
from .package import SubPackageLoader

from ..util import identity
from ..util.collections import OrderedDict, Mapping
from ..util.importlib.abc import MetaPathFinder

from ..util.compat import *


def import_all(relative_dirnames, namespace, path=None, loaders_init=None):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using mybuild_importer.
    """

    with mybuild_importer.using_namespace(namespace, path,
                                          loaders_init) as ctx:
        return ctx.import_all(dirname.replace(os.path.sep, '.')
                              for dirname in relative_dirnames
                              if '.' not in dirname)


def normalize_loaders(loaders=None):
    return_all = (loaders is None or '*' in loaders)

    is_map = isinstance(loaders, Mapping)
    if is_map:
        default = loaders.get('*', {})

    ret_type = (dict if is_map else set)
    return ret_type(((name, loaders.get(name, default)) if is_map else name)
                    for name in mybuild_importer.registered_loaders
                    if return_all or name in loaders)


def loader_filenames(loaders=None):
    return dict((name, getattr(mybuild_importer.registered_loaders[name],
                               'FILENAME', name))
               for name in normalize_loaders(loaders))


class MybuildImporter(MetaPathFinder):
    """
    PEP 302 meta path import hook. Use a singleton instance defined below.
    """

    class Context(object):
        """Context is an object associated with a namespace.

        Do not instantiate directly, use MybuildImporter.using_namespace()
        context manager instead.
        """

        def __init__(self, namespace):
            super(MybuildImporter.Context, self).__init__()
            self.namespace = namespace

            self.path = self.loaders = None  # initialized manually

        def import_all(self, rel_names=[], silent=False):
            ns = self.namespace
            ns_module = __import__(ns)

            for rel_name in rel_names:
                try:
                    __import__(ns + '.' + rel_name)
                except ImportError:
                    if not silent:
                        raise

            return ns_module

    def __init__(self):
        super(MybuildImporter, self).__init__()
        self._namespaces = OrderedDict()
        self.registered_loaders = dict()

    @contextlib.contextmanager
    def using_namespace(self, namespace, path=None, loaders_init=None):
        """
        Three things to do here. Upon completion, everithing is restored in
        a reversed order:
          1. Tell registered loaders about a new context
          2. Install ourselves into sys.meta_path, if needed
          3. Adjust internal namespace mapping
        """

        if '.' in namespace:
            raise NotImplementedError('To keep things simple')

        ctx = self.Context(namespace)

        ctx.path = list(path) if path is not None else []
        ctx.loaders = loaders = dict()  # populated below

        for name, initials in iteritems(normalize_loaders(loaders_init)):
            loader_type = self.registered_loaders[name]
            if hasattr(loader_type, 'init_ctx'):
                loader_ctx = loader_type.init_ctx(ctx, initials)
            else:
                loader_ctx = ctx
            loaders[name] = (loader_type, loader_ctx)

        nsmap = self._namespaces
        if not nsmap and self not in sys.meta_path:
            sys.meta_path.insert(0, self)

        saved = nsmap.get(namespace)
        nsmap[namespace] = ctx

        try:
            yield ctx  # import, import, import...

        finally:
            if saved is not None:
                nsmap[namespace] = saved
            else:
                del nsmap[namespace]

            if not nsmap and self in sys.meta_path:
                sys.meta_path.remove(self)

            for name, (loader_type, loader_ctx) in iteritems(ctx.loaders):
                if hasattr(loader_type, 'exit_ctx'):
                    loader_type.exit_ctx(loader_ctx)

    def loader_for(self, name):
        """
        Deco-maker for registering loaders.
        """

        def decorator(loader_type):
            """
            loader_type must be a loader factory which accepts three args:
                ctx: associated context
                fullname (str): fully.qualified.name of a module to load
                path (str): a file path

            loader_type may also provide two optional class methods:
                init_ctx:
                    Accepts an importer context object and user-provided
                    initials. Return value then replaces the first argument to
                    the factory (ctx).
                exit_ctx:
                    Called upon exiting a context with a single argument which
                    is the value returned by init_ctx (if any) or the importer
                    context object.

            If loader_type defines an optional FILENAME class attribute, it is
            used instead of the 'name' when searching a file.
            """
            if name in self.registered_loaders:
                prev = self.registered_loaders[name]
                raise ValueError("Loader for '{name}' is already registered "
                                 "{prev}".format(**locals()))

            self.registered_loaders[name] = loader_type

            return loader_type

        return decorator

    def find_module(self, fullname, path=None):
        """
        Try to find a loader for the specified module.

        Args:
            fullname (str): 'fully.qualified.name'
            path (list or None):
                None - when importing namespace root package
                ctx.path - importing anything within a namespace package
                pkg.__path__ - within a regular (sub-)package;

        Returns:
            A loader if the module has been located, None otherwise.

        For example, to import 'ns.pkg.PYBUILD' inside 'ns', this method gets
        called three times:

            fullname           path           returns
            ----------------   ------------   ----------------------
            'ns'               None           NamespacePackageLoader
            'ns.pkg'           ctx.path       SubPackageLoader
            'ns.pkg.PYBUILD'   pkg.__path__   PybuildFileLoader
        """

        namespace, _, restname = fullname.partition('.')
        try:
            ctx = self._namespaces[namespace]
        except KeyError:
            return None

        if not restname:
            return NamespacePackageLoader(ctx)

        tailname = restname.rpartition('.')[2]
        try:
            loader_type, loader_ctx = ctx.loaders[tailname]

        except KeyError:
            def find_loader_in(entry):
                basepath = os.path.join(entry, tailname)
                if os.path.isdir(basepath):
                    return SubPackageLoader(ctx, [basepath])
        else:
            filename = getattr(loader_type, 'FILENAME', tailname)
            def find_loader_in(entry):
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(loader_ctx, fullname, filepath)

        for loader in map(find_loader_in, path or sys.path):
            if loader is not None:
                return loader


mybuild_importer = MybuildImporter()  # singleton instance



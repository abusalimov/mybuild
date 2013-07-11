"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

import contextlib
import functools
import sys
import os.path

from .package import NamespacePackageLoader
from .package import SubPackageLoader

from ..util import identity
from ..util.collections import OrderedDict
from ..util.importlib.abc import MetaPathFinder

from ..util.compat import *


def import_all(relative_dirnames, namespace, path=None, defaults=None):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using mybuild_importer.
    """

    with mybuild_importer.using_namespace(namespace, path) as ctx:
        ctx.defaults=defaults
        return ctx.import_all(dirname.replace(os.path.sep, '.')
                              for dirname in relative_dirnames
                              if '.' not in dirname)


class MybuildImporter(MetaPathFinder):
    """
    PEP 302 meta path import hook. Use a singleton instance defined below.
    """

    class Context(object):
        """Context is an object associated with a namespace.

        Do not instantiate directly, use MybuildImporter.using_namespace()
        context manager instead.
        """

        def __init__(self, namespace, path, loaders):
            super(MybuildImporter.Context, self).__init__()
            self.namespace = namespace
            self.path      = path
            self.loaders   = loaders

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
        self._loaders    = dict()

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

        path = list(path) if path is not None else []
        loaders = dict()  # populated below
        ctx = self.Context(namespace, path, loaders)

        init_kwargs = {}
        for name, loader_type in iteritems(self._loaders):
            if loaders_init is not None:
                try:
                    init_kwargs = loaders_init[name]
                except KeyError:
                    continue
            ctx_init_func = getattr(loader_type, 'enter_ctx', identity)
            loaders[name] = (loader_type, ctx_init_func(ctx, **init_kwargs))

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

            for name, (loader_type, lctx) in iteritems(ctx.loaders):
                if hasattr(loader_type, 'exit_ctx'):
                    loader_type.exit_ctx(lctx)

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
                enter_ctx:
                    Accepts an importer context object, its return value is
                    then replaces the first argument to the factory (ctx).
                exit_ctx:
                    TODO

            If loader_type defines an optional FILENAME class attribute, it is
            used instead of the 'name' when searching a file.
            """
            if name in self._loaders:
                prev = self._loaders[name]
                raise ValueError("Loader for '{name}' is already registered "
                                 "{prev}".format(**locals()))

            self._loaders[name] = loader_type

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

        For example, to import 'ns.pkg.PYBUILD' inside 'ns', this method is
        called four times:

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
            loader_type, lctx = ctx.loaders[tailname]

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
                    return loader_type(lctx, fullname, filepath)

        for loader in map(find_loader_in, path or sys.path):
            if loader is not None:
                return loader


mybuild_importer = MybuildImporter()  # singleton instance



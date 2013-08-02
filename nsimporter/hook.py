"""
Defines meta hook for importing namespaces.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-06-26"

__all__ = [
    "NamespaceImportHook",
]


import contextlib
import sys
import os.path

from .package import NamespacePackageLoader
from .package import SubPackageLoader

from util.collections import OrderedDict, Mapping
from util.importlib.abc import MetaPathFinder

from util.compat import *


class Loader(object):
    """NamespaceImportHook-compatible loader extension protocol.

    This class is mainly serves documentation purposes, there is no need to
    extend it.

    Two optional class attribute are recognized:
        MODULE:
            Used to identify the loader by a module name within a package.
            Defaults to __name__ of the loader class
        FILENAME:
            Used to locate a file within directories in a path.
            Defaults to MODULE

    Every method defined below is also optional.
    """

    @classmethod
    def init_ctx(cls, ctx, initials):
        """Accepts an importer context object and user-provided initials.
        Return value then replaces the first argument to __init__ (ctx).
        """
        return ctx

    @classmethod
    def exit_ctx(cls, ctx):
        """Called upon exiting a context with a single argument which is
        the value returned by init_ctx (if any) or the importer context object.
        """
        pass

    def __init__(self, ctx, fullname, path):
        """
        Args:
            ctx: associated context (see notes to init_ctx)
            fullname (str): fully.qualified.name of a module to load
            path (str): a file path
        """
        super(Loader, self).__init__()


def loader_module(loader):
    try:
        return loader.MODULE
    except AttributeError:
        return loader.__name__

def loader_filename(loader):
    try:
        return loader.FILENAME
    except AttributeError:
        return loader_module(loader)


class NamespaceImportHook(MetaPathFinder):
    """
    PEP 302 meta path import hook.
    """

    class Context(object):
        """Context is an object associated with a namespace.

        Do not instantiate directly, use NamespaceImportHook.using_namespace()
        context manager instead.
        """

        def __init__(self, namespace):
            super(NamespaceImportHook.Context, self).__init__()
            self.namespace = namespace

            self.path = self.loaders = None  # initialized manually

        def import_namespace(self):
            return __import__(self.namespace)

        def import_all(self, rel_names=[], silent=False):
            ns = self.namespace
            ns_module = self.import_namespace()  # do it first

            for rel_name in rel_names:
                try:
                    __import__(ns + '.' + rel_name)
                except ImportError:
                    if not silent:
                        raise

            return ns_module

    def __init__(self):
        super(NamespaceImportHook, self).__init__()
        self._namespaces = OrderedDict()

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

        for loader_type, initials in iteritems(loaders_init):
            if hasattr(loader_type, 'init_ctx'):
                loader_ctx = loader_type.init_ctx(ctx, initials)
            else:
                loader_ctx = ctx
            name = loader_module(loader_type)
            try:
                old_loader_type, _ = loaders[name]
            except KeyError:
                loaders[name] = loader_type, loader_ctx
            else:
                raise ValueError(
                        "Conflicting name '%s' for loader types "
                        "'%s' and '%s'" % (name, old_loader_type, loader_type))

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

        for loader_type, loader_ctx in itervalues(ctx.loaders):
            if hasattr(loader_type, 'exit_ctx'):
                loader_type.exit_ctx(loader_ctx)

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
            'ns.pkg.PYBUILD'   pkg.__path__   PyFileLoader
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
            filename = loader_filename(loader_type)
            def find_loader_in(entry):
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(loader_ctx, fullname, filepath)

        for loader in map(find_loader_in, path or sys.path):
            if loader is not None:
                return loader


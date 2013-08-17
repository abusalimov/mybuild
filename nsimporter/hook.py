"""
Defines meta hook for importing namespaces.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-06-26"

__all__ = [
    "NamespaceImportHook",
    "NamespaceContextManager",
]


from _compat import *

import sys
import os.path

from nsimporter.package import PackageLoader

from util.importlib.abc import MetaPathFinder


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
    def init_ctx(cls, importer, initials):
        """Accepts an importer object and user-provided initials.
        Return value then replaces the first argument to __init__ (importer).
        """
        return importer

    @classmethod
    def exit_ctx(cls, importer):
        """Called upon exiting an importer context with a single argument which
        is the value returned by init_ctx (if any) or the importer object.
        """
        pass

    def __init__(self, importer, fullname, path):
        """
        Args:
            importer: an associated importer (see notes to init_ctx)
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

    def __init__(self, namespace, path=None):
        super(NamespaceImportHook, self).__init__()

        if '.' in namespace:
            raise NotImplementedError('To keep things simple')

        self.namespace = namespace
        self.path = list(path) if path is not None else []

    def _init_loaders(self, loaders_init={}):
        """Prepares loaders by creating a context for each of them.

        Must be called prior to installing self into sys.meta_path."""

        loaders = dict()

        for loader_type, initials in iteritems(loaders_init):
            if hasattr(loader_type, 'init_ctx'):
                loader_ctx = loader_type.init_ctx(self, initials)
            else:
                loader_ctx = self

            name = loader_module(loader_type)
            if name in loaders:
                raise ValueError("Conflicting name '{name}' for loader types "
                                 "'{loaders[name][0]}' and '{loader_type}'"
                                 .format(**locals()))

            loaders[name] = loader_type, loader_ctx

        self.loaders = loaders

    def _exit_loaders(self):
        """Finalizes loader contexts."""
        for loader_type, loader_ctx in itervalues(self.loaders):
            if hasattr(loader_type, 'exit_ctx'):
                loader_type.exit_ctx(loader_ctx)

    def find_module(self, fullname, path=None):
        """
        Try to find a loader for the specified module.

        Args:
            fullname (str): 'fully.qualified.name'
            path (list or None):
                None - when importing namespace root package
                self.path - importing anything within a namespace package
                pkg.__path__ - within a regular (sub-)package;

        Returns:
            A loader if the module has been located, None otherwise.

        For example, to import 'ns.pkg.PYBUILD' inside 'ns', this method gets
        called three times:

            fullname           path           returns
            ----------------   ------------   ----------------------
            'ns'               None           PackageLoader
            'ns.pkg'           self.path      PackageLoader
            'ns.pkg.PYBUILD'   pkg.__path__   PyFileLoader
        """
        namespace, _, restname = fullname.partition('.')

        if namespace != self.namespace:
            return None
        if not restname:
            return PackageLoader(self.path, self.loaders)

        tailname = restname.rpartition('.')[2]
        try:
            loader_type, loader_ctx = self.loaders[tailname]

        except KeyError:
            def find_loader_in(entry):
                basepath = os.path.join(entry, tailname)
                if os.path.isdir(basepath):
                    return PackageLoader([basepath], self.loaders)
        else:
            filename = loader_filename(loader_type)
            def find_loader_in(entry):
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(loader_ctx, fullname, filepath)

        for loader in map(find_loader_in, path or sys.path):
            if loader is not None:
                return loader


class NamespaceContextManager(NamespaceImportHook):
    """
    PEP 343 context manager.
    """

    def __init__(self, namespace, path=None, loaders_init=None):
        super(NamespaceContextManager, self).__init__(namespace, path)
        self.loaders_init = (dict(loaders_init)
                             if loaders_init is not None else {})

    def __enter__(self):
        self._init_loaders(self.loaders_init)
        sys.meta_path.insert(0, self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        if exc_type is None:
            self._exit_loaders()


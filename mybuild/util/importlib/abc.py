"""
Abstract base classes related to import. Primarily for documentation purposes.
"""

from __future__ import absolute_import

import abc

from ..compat import *


# Everything below is derived from py3k importlib.abc

class MetaPathFinder(ABCBase):
    """Abstract base class for import finders on sys.meta_path."""

    @abc.abstractmethod
    def find_module(self, fullname, path):
        """Abstract method which, when implemented, should find a module.
        The fullname is a str and the path is a str or None.
        Returns a Loader object.
        """
        raise NotImplementedError


# PathEntryFinder class is not implemented as unused.


class Loader(ABCBase):
    """Abstract base class for import loaders."""

    @abc.abstractmethod
    def load_module(self, fullname):
        """Abstract method which when implemented should load a module.
        The fullname is a str."""
        raise NotImplementedError

    # @abc.abstractmethod
    # def module_repr(self, module):
    #     """Abstract method which when implemented calculates and returns the
    #     given module's repr."""
    #     raise NotImplementedError


class ResourceLoader(Loader):
    """Abstract base class for loaders which can return data from their
    back-end storage."""

    @abc.abstractmethod
    def get_data(self, path):
        """Abstract method which when implemented should return the bytes for
        the specified path.  The path must be a str."""
        raise NotImplementedError


class InspectLoader(Loader):
    """Abstract base class for loaders which support inspection about the
    modules they can load."""

    @abc.abstractmethod
    def is_package(self, fullname):
        """Abstract method which when implemented should return whether the
        module is a package.  The fullname is a str.  Returns a bool."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_code(self, fullname):
        """Abstract method which when implemented should return the code object
        for the module.  The fullname is a str.  Returns a types.CodeType."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_source(self, fullname):
        """Abstract method which should return the source code for the
        module.  The fullname is a str.  Returns a str."""
        raise NotImplementedError


class ExecutionLoader(InspectLoader):
    """Abstract base class for loaders that wish to support the execution of
    modules as scripts."""

    @abc.abstractmethod
    def get_filename(self, fullname):
        """Abstract method which should return the value that __file__ is to be
        set to."""
        raise NotImplementedError


class SourceLoader(ResourceLoader, ExecutionLoader):
    """Abstract base class for loading source code.

    Note: this backport ABC defines no bytecode-related methods.
    """

    def get_source(self, fullname):
        """Concrete implementation of InspectLoader.get_source."""
        path = self.get_filename(fullname)
        try:
            source_bytes = self.get_data(path)
        except IOError:
            raise ImportError("source not available through get_data()")
        return source_bytes  # XXX proper encoding

    def get_code(self, fullname):
        """Reads a source using Loader.get_data and returns complied code. """
        source_path = self.get_filename(fullname)
        source_bytes = self.get_data(source_path)
        code_object = compile(source_bytes, source_path, 'exec',
                                dont_inherit=True)
        return code_object



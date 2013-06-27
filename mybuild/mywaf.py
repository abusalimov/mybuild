"""
Mybuild tool for Waf.
"""

import abc
import functools
import imp
import sys
import os

from waflib import Context as wafcontext
from waflib import Utils   as wafutils

def options(ctx):
	print('mywaf: %r' % ctx)

def configure(ctx):
	print('mywaf: %r' % ctx)

def load_myfiles(ctx, myfile_names, root_node=None):
	if root_node is None:
		root_node = ctx.path
	myfiles_glob = ['**/' + f for f in wafutils.to_list(myfile_names)]
	files = root_node.ant_glob(myfiles_glob)
	print files

wafcontext.Context.load_myfiles = load_myfiles

# Everything below is derived from py3k importlib.

class SourceLoader(object):
    __metaclass__ = abc.ABCMeta
    """Generic Python source loader."""

    def load_module(self, name):
        module = sys.modules.get(name)

        is_reload = bool(module)
        if not is_reload:
            module = self._new_module(name)
            sys.modules[name] = module

        try:
            self._init_module(module)
        except:
            if not is_reload:
                del sys.modules[name]
            raise

        return module

    def _new_module(self, name):
        return imp.new_module(name)

    def _init_module(self, module):
        name = module.__name__
        code_object = self.get_code(name)

        module.__file__ = self.get_filename(name)
        module.__package__ = name
        if self.is_package(name):
            module.__path__ = [self._get_path(module.__file__)]
        else:
            module.__package__ = module.__package__.rpartition('.')[0]
        module.__loader__ = self

        exec(code_object, module.__dict__)

    def is_package(self, name):
        """Everything is assumed to be a package. No modules."""
        return True

    def get_source(self, name):
        """Concrete implementation of InspectLoader.get_source."""
        path = self.get_filename(name)
        try:
            source_bytes = self.get_data(path)
        except IOError:
            raise ImportError("source not available through get_data()")
        return source_bytes.decode(encoding[0])

    def get_code(self, name):
        """Reads a source using Loader.get_data and returns complied code. """
        source_path = self.get_filename(name)
        source_bytes = self.get_data(source_path)
        code_object = compile(source_bytes, source_path, 'exec',
                                dont_inherit=True)
        return code_object

    @abc.abstractmethod
    def get_filename(self, name):
        raise NotImplementedError
    @abc.abstractmethod
    def get_data(self, path):
        raise NotImplementedError
    @abc.abstractmethod
    def _get_path(self, filename):
        raise NotImplementedError


def _check_arg(attr):
    """Deco-maker to verify that the module being requested matches the
    one the loader can handle.

    The first argument (self) must define an attr which the second argument
    is compared against. If the comparison fails then ImportError is
    raised.
    """
    def decorator(fxn):
        @functools.wraps(fxn)
        def decorated(self, arg, *args, **kwargs):
            if getattr(self, attr) != arg:
                raise ImportError("loader for %s %s cannot handle %s" %
                                  (attr, getattr(self, attr), arg))
            return fxn(self, arg, *args, **kwargs)
        return decorated
    return decorator


class FileLoader(object):

    """Base file loader class which implements the loader protocol methods that
    require file system usage."""

    def __init__(self, name, filename):
        """Cache the module name and the path to the file found by the
        finder."""
        super(FileLoader, self).__init__()
        self.name = name
        self.filename = filename

    @_check_arg('name')
    def get_filename(self, name):
        """Return the path to the source file as found by the finder."""
        return self.filename

    @_check_arg('filename')
    def get_data(self, filename):
        """Return the data from path as raw bytes."""
        with open(filename, 'rb') as f:
            return f.read()

    @_check_arg('filename')
    def _get_path(self, filename):
        return os.path.dirname(filename)


class SourceFileLoader(FileLoader, SourceLoader):
    """Concrete implementation of SourceLoader using the file system."""

class ManifestFileLoader(SourceFileLoader):
    """docstring for ManifestFileLoader"""

class MybuildFileLoader(SourceFileLoader):
    """docstring for MybuildFileLoader"""

    def _new_module(self, name):
        module = super(MybuildFileLoader, self)._new_module(name)

        try:
            manifest = sys.modules[name.partition('.')[0]]
        except KeyError:
            raise ImportError('Manifest is not loaded for %s' % name)

        if hasattr(manifest, '__all__'):
            attrs = manifest.__all__
        else:
            attrs = [attr for attr in dir(manifest)
                     if not attr.startswith('_')]

        for attr in attrs:
            setattr(module, attr, getattr(manifest, attr))

        return module

class MyFileFinder(object):

    MANIFEST_SUFFIX = '.MYMANIFEST'
    MYBUILD_FILENAME = 'Pybuild'

    def __init__(self, path):
        super(MyFileFinder, self).__init__()
        self.path = path

    def find_module(self, name):
        """Try to find a loader for the specified 'fully.qualified.name'."""
        if not name.partition('.')[1]:
            return self.find_manifest(name)
        else:
            return self.find_mybuild(name)

    def find_manifest(self, name):
        assert '.' not in name
        filename = os.path.join(self.path, name + self.MANIFEST_SUFFIX)
        if os.path.isfile(filename):
            return ManifestFileLoader(name, filename)

    def find_mybuild(self, name):
        tailname = name.rpartition('.')[2]
        basepath = os.path.join(self.path, tailname)

        if os.path.isdir(basepath):
            filename = os.path.join(basepath, self.MYBUILD_FILENAME)
            if os.path.isfile(filename):
                return MybuildFileLoader(name, filename)


if MyFileFinder not in sys.path_hooks:
    sys.path_hooks.insert(0, MyFileFinder)


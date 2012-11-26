#! /usr/bin/python

"""
Fixup for case of invoking modules from a subpackage directory.
Taken for PEP395: http://www.python.org/dev/peps/pep-0395/
"""

import imp
import os
import sys
import runpy

def _splitmodname(fspath):
    path_entry, fname = os.path.split(fspath)
    modname = os.path.splitext(fname)[0]
    return path_entry, modname

def _is_package_dir(fspath):
    return any(os.path.exists(os.path.join(fspath, "__init__" + info[0]))
               for info in imp.get_suffixes())

def split_path_module(fspath, modname=None):
    """Given a filesystem path and a relative module name, determine an
       appropriate sys.path entry and a fully qualified module name.

       Returns a 3-tuple of (package_depth, fspath, modname). A reported
       package depth of 0 indicates that this would be a top level import.

       If no relative module name is given, it is derived from the final
       component in the supplied path with the extension stripped.
    """
    fspath = os.path.abspath(fspath)
    if modname is None:
        fspath, modname = _splitmodname(fspath)

    package_depth = 0
    while _is_package_dir(fspath):
        fspath, pkg = _splitmodname(fspath)
        modname = pkg + '.' + modname
        package_depth += 1
    return package_depth, fspath, modname

if __name__ == '__main__':
    # Direct script execution
    if len(sys.argv) < 2:
        print >> sys.stderr, "%s: No script specified" % sys.argv[0]
        sys.exit(1)

    del sys.argv[0] # Make the requested module sys.argv[0]

    in_package, path_entry, modname = split_path_module(sys.argv[0])
    sys.path.insert(0, path_entry)
    if in_package:
        runpy._run_module_as_main(modname)
    else:
        runpy.run_path(sys.argv[0], run_name='__main__')

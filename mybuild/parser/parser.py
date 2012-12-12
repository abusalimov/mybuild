
__author__ = "Anton Kozlov"
__date__ = "2012-12-12"

from mybuild import module, option
from mybuild.constraints import Constraints

import sys

def package(name):
    import types
    global pkg
    pkg = sys.modules[__name__]
    for subpkg in name.split('.'):
	if not hasattr(pkg, name):
	    pkg.__dict__[name] = types.ModuleType(subpkg)
	pkg = getattr(pkg, name)

def mod(name, *args, **kargs):
    def mod_dec(name_overwrite):
	def f(fn):
	    fn.__name__ = name_overwrite
	    return module(fn)

	return f

    @mod_dec(name)
    def new_mod(self):
	pass

    global pkg
    pkg.__dict__[name] = new_mod

def main(argv):
    glob = globals().copy()
    locl = {}

    for arg in argv:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.my') or file == 'Mybuild':
		    execfile(os.path.join(dirpath, file),glob, locl)

if __name__ == '__main__':
    import os
    main(sys.argv[1:])

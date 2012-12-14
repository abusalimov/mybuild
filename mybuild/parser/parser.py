
__author__ = "Anton Kozlov"
__date__ = "2012-12-12"

from mybuild import module as mybuild_module, option
from mybuild.constraints import Constraints

def package(name):
    import types
    import sys
    import config
   
    pkg = config.root

    for subpkg in name.split('.'):
	if not hasattr(pkg, name):
	    pkg.__dict__[name] = types.ModuleType(subpkg)
	pkg = getattr(pkg, name)

    global this_pkg
    this_pkg = pkg

def module(name, *args, **kargs):
    def mod_dec(name_overwrite):
	def f(fn):
	    fn.__name__ = name_overwrite
	    return mybuild_module(fn)

	return f

    @mod_dec(name)
    def new_mod(self):
	pass

    this_pkg.__dict__[name] = new_mod

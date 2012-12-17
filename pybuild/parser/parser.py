
from .. package import Package
from .. module  import Module

from mybuild.common import pkg

def root_pkg():
    return Package('root', None)

def prepare_build(root):
    modlist = pkg.modlist(root, Package, Module, lambda pkg: pkg.items())
    print '\n'.join(modlist)
    return modlist

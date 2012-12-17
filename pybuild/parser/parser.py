
from .. module  import Module

import common.pkg

def root_pkg():
    return Package('root', None)

def prepare_build(root):
    modlist = common.pkg.modlist(root, Package, Module, lambda pkg: pkg.items())
    print '\n'.join(modlist)
    return modlist

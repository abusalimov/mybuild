
from mybuild.common import pkg

def prepare_build(root):
    modlist = pkg.modlist(root, Package, Module, lambda pkg: pkg.items())
    print '\n'.join(modlist)
    return modlist


__author__ = "Anton Kozlov"
__date__ = "2012-12-14"

import sys

import mybuild

from mybuild.parser.parser import *

def root_pkg():
    import types 
    return types.ModuleType('root')

def config(root):
    import types 
    config = types.ModuleType('config')
    
    config.__dict__['root'] = root
    return config

def main(argv):
    glob = globals().copy()
    locl = {}

    root = root_pkg()

    sys.modules['config'] = config(root)

    for arg in argv:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.my') or file == 'Mybuild':
		    execfile(os.path.join(dirpath, file), glob, locl)

    print root.myprog.init1

if __name__ == '__main__':
    import os
    main(sys.argv[1:])

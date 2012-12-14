
__author__ = "Anton Kozlov"
__date__ = "2012-12-14"

import sys

if __name__ == '__main__':
    import argparse
    argparser = argparse.ArgumentParser('parser')
    argparser.add_argument('--method', choices="AE", required = True, 
	    help='Model method, either A (for Anton\'s) or E (for Eldar\'s')
    argparser.add_argument('DIR', nargs='+', 
	    help='Directory where Mybuilds will be searched')
    args = argparser.parse_args()

    if args.method == 'A':
	from pybuild.parser import *
	from pybuild.option import Integer, List
    elif args.method == 'E':
	from mybuild.parser.parser import *

def config(root):
    import types 
    config = types.ModuleType('config')
    
    config.__dict__['root'] = root
    config.__dict__['dirname'] = ''
    config.__dict__['modlist'] = []
    return config

def main(args):
    import os

    glob = globals().copy()
    locl = {}

    root = root_pkg()
    cfg  = config(root)

    sys.modules['config'] = config(root)

    for arg in args.DIR:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.py') or file == 'Pybuild':
		    cfg.dirname = dirpath
		    execfile(os.path.join(dirpath, file), glob, locl)

    prepare_build(root)

if __name__ == '__main__':
    main(args)

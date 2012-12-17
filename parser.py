
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
	from pybuild.parser.mod_rules import *
	from pybuild.parser.parser import root_pkg, prepare_build
	
    elif args.method == 'E':
	from mybuild.parser.mod_rules import *
	from mybuild.parser.parser import root_pkg, prepare_build

def parse(args):
    def build_ctx(root):
	import types 
	config = types.ModuleType('build_ctx')
	
	config.__dict__['root'] = root
	config.__dict__['dirname'] = ''
	config.__dict__['modlist'] = []
	return config

    import os

    glob = globals().copy()
    locl = {}

    root = root_pkg()
    ctx  = build_ctx(root)

    sys.modules['build_ctx'] = ctx

    for arg in args.DIR:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.py') or file == 'Pybuild':
		    ctx.dirname = dirpath
		    execfile(os.path.join(dirpath, file), glob, locl)

    return prepare_build(root)

if __name__ == '__main__':
    parse(args)

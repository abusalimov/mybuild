
__author__ = "Anton Kozlov"
__date__ = "2012-12-14"

import os
import sys
import re

def parse(mod_dirs, cfg_dir, method ='A'):
    #class BuildCtx(types.ModuleType):
    def build_ctx(root):
	import types 
	config = types.ModuleType('build_ctx')
	d = config.__dict__
	init = [('root', root),
		('dirname', ''),
		('modlist', []),
		('ld_defs', []),
		('modconstr', []),
		]
	for name, initval in init:
	    setattr(config, name, initval)
	return config

    def imp_all(scope, modname, fromlist):
	mod = __import__(modname, scope, scope, fromlist, -1)
	for k in dir(mod):
	    if not re.match('__.*__', k):
		scope[k] = getattr(mod, k)

    if method == 'A':
	from pybuild.parser.parser import root_pkg, prepare_build
    elif method == 'E':
	from mybuild.parser.parser import root_pkg, prepare_build

    root = root_pkg()
    ctx  = build_ctx(root)

    sys.modules['build_ctx'] = ctx

    locl = {}
    glob = globals()

    if method == 'A':
	imp_all(glob, 'pybuild.parser.mod_rules', ['*'])
	imp_all(glob, 'pybuild.parser.cfg_rules', ['*'])
	imp_all(glob, 'pybuild.parser.build_ops', ['*'])
	
    elif method == 'E':
	imp_all(glob, 'mybuild.parser.mod_rules', ['*'])
	imp_all(glob, 'mybuild.parser.cfg_rules', ['*'])

    for arg in [cfg_dir] + mod_dirs:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.py') or file == 'Pybuild':
		    ctx.dirname = dirpath
		    execfile(os.path.join(dirpath, file), glob)

    return ctx

if __name__ == '__main__':
    import argparse
    argparser = argparse.ArgumentParser('parser')
    argparser.add_argument('--method', choices="AE", required = True, 
	    help='Model method, either A (for Anton\'s) or E (for Eldar\'s')
    argparser.add_argument('--config')
    argparser.add_argument('DIR', nargs='+', 
	    help='Directory where Mybuilds will be searched')
    args = argparser.parse_args()

    parse(args.DIR, args.config, args.method)

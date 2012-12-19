
__author__ = "Anton Kozlov"
__date__ = "2012-12-14"

import os
import sys
import re
import types 

class BuildCtx(types.ModuleType):
    def __init__(self):
        super(BuildCtx, self).__init__('build_ctx')

def parse(ctx, mod_dirs, method ='A'):
    def imp_all(scope, modname, fromlist):
        mod = __import__(modname, scope, scope, fromlist, -1)
        for k in dir(mod):
            if not re.match('__.*__', k):
                scope[k] = getattr(mod, k)

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

    for arg in mod_dirs:
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
    argparser.add_argument('DIR', nargs='+', 
            help='Directory where Mybuilds will be searched')
    args = argparser.parse_args()

    if args.method == 'A':
        from pybuild.method import method_pre_parse
    elif args.method == 'E':
        from mybuild.method import method_pre_parse

    ctx = method_pre_parse(BuildCtx())
    ctx = parse(ctx, args.DIR, args.method)

    print dir(ctx)
    print ctx.root

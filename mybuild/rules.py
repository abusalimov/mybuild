import types

from mybuild.mybuild import module as mybuild_module, option
from mybuild.mybuild.constraints import Constraints

from mybuild.common.rules import ModRules as CommonModRules, CfgRules as CommonCfgRules

class ModRules(CommonModRules):
    def package(self, name):
        import build_ctx 

        pkg = build_ctx.root

        for subpkg in name.split('.'):
            if not hasattr(pkg, subpkg):
                setattr(pkg, subpkg, types.ModuleType(subpkg))
            pkg = getattr(pkg, subpkg)

        global this_pkg
        this_pkg = pkg

    def convert_opt(self, opt):
        return '%s = option(%s)' % (opt.name, getattr(opt, 'default', ''))

    def module(self, name, *args, **kargs):
        opts_def = ', '.join(map(self.convert_opt, kargs.get('options', [])))
        opts_name = ', '.join([opt.name for opt in kargs.get('options', [])])
        
        CommonModRules.module_helper(self, name, args, kargs)

        fn_decl = '''
def create_mod(fn):
    def {MOD_NAME}(inst, {OPTIONS}):
        fn(inst, {OPTS_NAME})
    return {MOD_NAME}

        '''.format(MOD_NAME=name, OPTIONS = opts_def, OPTS_NAME=opts_name)

        print fn_decl
    
        exec fn_decl in globals(), locals()

        def body(inst, *args):
            inst.sources = kargs.get('sources', [])
            inst.qualified_name = name
            
        call = create_mod(body)

        mod = mybuild_module(call)

        setattr(this_pkg, name, mod)

        return mod

class CfgRules(CommonCfgRules):
    def include(self, name, opts = {}, runlevel = 2): 
        import build_ctx
        build_ctx.constr.append((name, opts))

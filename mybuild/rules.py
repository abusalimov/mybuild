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
        opts = ', '.join(map(self.convert_opt, kargs.get('options', [])))
        
        CommonModRules.module_helper(self, name, args, kargs)

        fn_decl = '''
def create_mod(sources, qualified_name):
    def {MOD_NAME}(inst, {OPTIONS}):
        inst.sources = sources
        inst.qualified_name = qualified_name
    return {MOD_NAME}

        '''.format(MOD_NAME=name, OPTIONS = opts)

        print fn_decl
    
        exec fn_decl

        call = create_mod(kargs.get('sources', []), name)

        mod = mybuild_module(call)

        setattr(this_pkg, name, mod)

        return mod

class CfgRules(CommonCfgRules):
    def include(self, name, opts = {}, runlevel = 2): 
        import build_ctx
        build_ctx.constr.append((name, opts))

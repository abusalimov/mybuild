import types

from mybuild.mybuild import module as mybuild_module, option
from mybuild.mybuild.constraints import Constraints

from mybuild.common.rules import ModRules as CommonModRules

class ModRules(CommonModRules):
    def package(self, name):
        import sys
        import build_ctx 

        pkg = build_ctx.root

        for subpkg in name.split('.'):
            if not hasattr(pkg, subpkg):
                setattr(pkg, subpkg, types.ModuleType(subpkg))
            pkg = getattr(pkg, subpkg)

        global this_pkg
        this_pkg = pkg

    def __convert_opt(opt):
        return '%s = option()' % (opt.name)

    def module(self, name, *args, **kargs):
        opts = ', '.join(map(__convert_opt, kargs.get('options', [])))
        
        common_mod_rules.module(name, args, kargs)

        fn_decl = '''
    @mybuild_module
    def {MOD_NAME}(self, {OPTIONS}):
        pass
        '''.format(MOD_NAME=name, OPTIONS = opts)

        exec fn_decl

        mod = locals()[name]

        setattr(this_pkg, name, mod)

        return mod


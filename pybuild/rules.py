
from package import Package, obj_in_pkg
from module  import Module
from interface import Interface
from option import *

from domain import BoolDom

from mybuild.annotation import LDScript, Generated, NoRuntime, DefMacro, IncludePath

from mybuild.common.rules import ModRules as CommonModRules, CfgRules as CommonCfgRules

class ModRules(CommonModRules):
    def package(self, name):
        global package_name
        package_name = name

        import build_ctx
        ctx = build_ctx

        ctx.pkglist.add(ctx.root.built_subpack(name))

    def build_obj(self, cls, name, args, kargs):
        global package_name
        
        import build_ctx
        ctx = build_ctx
        ctx.modlist.append('.'.join ((package_name, name)))
        return obj_in_pkg(cls, ctx.root[package_name], name, *args, **kargs)

    def module(self, name, *args, **kargs):
        CommonModRules.module_helper(self, name, args, kargs)

        return self.build_obj(Module, name, args, kargs)

    def interface(self, name, *args, **kargs):
        return self.build_obj(Interface, name, args, kargs)

    def LDScript(self, file):
        return LDScript(file)

    def Generated(self, file, fn):
        return Generated(file, fn)

    def NoRuntime(self, mod):
        return NoRuntime(mod)

    def DefMacro(self, macro, src):
        return DefMacro(macro, src)

    def IncludePath(self, paths, srcs):
        return IncludePath(paths, srcs)

    def Integer(self, *args, **kargs):
        return Integer(*args, **kargs)

    def List(self, *args, **kargs):
        return List(*args, **kargs)


class CfgRules(CommonCfgRules):
    def include(self, name, opts={}, runlevel=2):
        import build_ctx
        ctx = build_ctx

        ctx.runlevels[runlevel].dependency_add(name, opts)

        ctx.modconstr.append((name, True))

        for opt_name, value in opts.items():
            ctx.modconstr.append(("%s.%s" % (name, opt_name), value))


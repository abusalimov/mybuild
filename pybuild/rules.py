
from mybuild.package import Package, obj_in_pkg
from module  import Module
from interface import Interface
from option import *

from domain import BoolDom

from mybuild.common.rules import ModRules as CommonModRules, CfgRules as CommonCfgRules

class ModRules(CommonModRules):
    def package(self, name):
        global package_name
        package_name = name

        import build_ctx
        ctx = build_ctx

        ctx.pkglist.add(ctx.root.build_subpack(name))

    def build_obj(self, cls, name, args, kargs):
        global package_name
        
        import build_ctx
        ctx = build_ctx
        ctx.modlist.append('.'.join ((package_name, name)))
        return obj_in_pkg(cls, getattr(ctx.root, package_name), name, *args, **kargs)

    def module(self, name, *args, **kargs):
        CommonModRules.module_helper(self, name, args, kargs)

        return self.build_obj(Module, name, args, kargs)

    def interface(self, name, *args, **kargs):
        return self.build_obj(Interface, name, args, kargs)

class CfgRules(CommonCfgRules):
    def include(self, name, **kargs):
        import build_ctx
        ctx = build_ctx

        if kargs.has_key('runlevel'):
            runlevel = kargs['runlevel']
            del kargs['runlevel']
            ctx.runlevels[runlevel].dependency_add(name, kargs)

        ctx.modconstr.append((name, True))

        for opt_name, value in kargs.items():
            ctx.modconstr.append(("%s.%s" % (name, opt_name), value))


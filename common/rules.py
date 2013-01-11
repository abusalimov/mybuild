from mybuild.pybuild.util import isvector

from mybuild.source     import Source
from mybuild.pybuild.option import Integer, Boolean, List, String

from mybuild.annotation import LDScript, Generated, \
        NoRuntime, DefMacro, IncludePath, InitFS

class ModRules():
    def module(self, name, *args, **kargs):
        pass

    def __process(self, kargs, fn, key):
        if kargs.has_key(key):
            flat = []
            for o in kargs[key]:
                if isvector(o):
                    flat += [fn(obj) for obj in o]
                else:
                    flat.append(fn(o))
            kargs[key] = flat

    def module_helper(self, name, args, kargs):
        import build_ctx
        ctx = build_ctx
        self.__process(kargs, lambda s: Source(ctx.dirname, s), 'sources')
        self.__process(kargs, lambda s: s, 'depends')

    def library(self, name, *args, **kargs):
        kargs['static'] = True
        return self.module(name, *args, **kargs)

    def runlevel(self, n, depends=[]):
        import build_ctx
        ctx = build_ctx
        ctx.runlevels[n] = self.module('runlevel%d' % (n,), depends = depends)
        return ctx.runlevels[n]

    def interface(self, name, *args, **kargs):
        return self.module(name, *args, **kargs)

    def LDScript(self, file):
        return LDScript(file)

    def Generated(self, file, fn):
        return Generated(file, fn)

    def NoRuntime(self, mod):
        return NoRuntime(mod)

    def DefMacro(self, macro, src):
        return DefMacro(macro, src)

    def InitFS(self, src):
        return InitFS(src)

    def IncludePath(self, paths, srcs):
        return IncludePath(paths, srcs)

    def Integer(self, *args, **kargs):
        return Integer(*args, **kargs)

    def List(self, *args, **kargs):
        return List(*args, **kargs)
    
    def String(self, *args, **kargs):
        return String(*args, **kargs)

class CfgRules():
    def lds_region(self, name, base, size):
        import build_ctx
        ctx = build_ctx
        ctx.ld_defs.append('LDS_REGION_BASE_%s=%s' % (name, base))
        ctx.ld_defs.append('LDS_REGION_SIZE_%s=%s' % (name, size))

    def lds_section_load(self, name, vma, lma):
        import build_ctx
        ctx = build_ctx
        ctx.ld_defs.append('LDS_SECTION_VMA_%s=%s' % (name, vma))
        ctx.ld_defs.append('LDS_SECTION_LMA_%s=%s' % (name, lma))

    def lds_section(self, name, reg):
        return self.lds_section_load(name, reg, reg)

    def include(self, name, **kargs):
        pass

    def exclude(self, name):
        pass


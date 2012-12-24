from mybuild.pybuild.util import isvector

from mybuild.source     import Source
from mybuild.pybuild.option import Integer, Boolean, List

class ModRules():
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

    def LDScript(self, file):
        return file

    def Generated(self, file, fn):
        return file 

    def NoRuntime(self, file):
        return file

    def DefMacro(self, macro, src):
        return src

    def IncludePath(self, paths, srcs):
        return srcs

    def Integer(self, *args, **kargs):
        return Integer(*args, **kargs)

    def List(self, *args, **kargs):
        return List(*args, **kargs)

class CfgRules():
    def lds_region(self, name, base, size):
        pass

    def lds_section_load(self, name, vma, lma):
        pass

    def lds_section(self, name, reg):
        pass

    def include(self, name, opts={}, runlevel=2):
        pass

    def exclude(self, name):
        pass



import os
import re

from annotation import *

class BuildSpec():
    def __init__(self, src, includes=[], defines=[]):
        self.src = src
        self.includes = includes
        self.defines = defines

class Source(object):
    def __init__(self, dirname, filename):
        self.dirname = dirname
        self.filename = filename

    def __repr__(self):
        return "Source('%s/%s')" % (self.dirname, self.filename)

    def fullpath(self):
        return os.path.join(self.dirname, self.filename)

    def annotations(self):
        anns = getattr(self.filename, 'annots', [])
        return anns

    def build(self, ctx, opt):
        f = BuildSpec(self.fullpath())

        for ann in self.annotations():
            f = ann.build(ctx, f, opt)

        return self.build_rule(f, ctx, opt)

    def build_rule(self, spec, ctx, opt):
        if not re.match('.*\.[cS]', spec.src):
            return spec.src 
        tgt = "%s.o" % (spec.src,)
        ctx.bld(
            features = 'c', 
            source = spec.src,
            target = tgt,
            defines = ['__EMBUILD_MOD__=%s' % (opt.qualified_name().replace('.', '__'),)] + spec.defines,
            includes = ctx.bld.env.includes + spec.includes,
        )
        return tgt 

import re
from mybuild.build import inchdr

class ModuleBuildOps(object):
    def build(self, ctx):
        if not self.isbuilding(ctx.model):
            return 

        srcs = []
        header_inc = []
        header_opts = []

        for src in self.get_sources():
            fsrc = src.build(ctx, self)
            if re.match('.*\.o', fsrc):
                srcs.append(fsrc)
            elif re.match('.*\.h', fsrc):
                header_inc.append(fsrc)

        for option in self.get_options():
            repr = option.build_repr()
            if not repr:
                continue
            header_opts.append(inchdr(repr, self.qualified_name(), option.name, option.value(ctx.model)))

        ctx.bld(features = 'module_header',
            name = self.qualified_name() + '_header',
            mod_name = self.qualified_name(),
            header_opts = header_opts,
            header_inc = header_inc)

        self.build_self(ctx, srcs)

    def build_self(self, ctx, srcs):
        tgt = self.qualified_name().replace('.', '_') 
        fts = 'c'

        if self.islib():
            fts += ' cstlib'
            for i in self.get_depends():
                if i.islib():
                    srcs.append(i.qualified_name().replace('.', '_'))


        ctx.bld(
            features = fts, 
            target = tgt,
            #defines = ['__EMBUILD_MOD__'],
            includes = ctx.bld.env.includes,
            use = srcs,
        )

        ctx.bld.out.append(tgt)


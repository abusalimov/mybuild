
from .. domain import *

def lds_region(name, base, size):
    import build_ctx
    ctx = build_ctx
    ctx.ld_defs.append('LDS_REGION_BASE_%s=%s' % (name, base))
    ctx.ld_defs.append('LDS_REGION_SIZE_%s=%s' % (name, size))

def lds_section_load(name, vma, lma):
    import build_ctx
    ctx = build_ctx
    ctx.ld_defs.append('LDS_SECTION_VMA_%s=%s' % (name, vma))
    ctx.ld_defs.append('LDS_SECTION_LMA_%s=%s' % (name, lma))

def lds_section(name, reg):
    lds_section_load(name, reg, reg)

def include(name, opts={}, runlevel=2):
    import build_ctx
    ctx = build_ctx

    ctx.runlevels[runlevel].dependency_add(name, opts)

    ctx.modconstr.append((name, BoolDom([True])))

    for opt_name, value in opts.items():
        ctx.modconstr.append(("%s.%s" % (name, opt_name), value))

def exclude(name):
    pass


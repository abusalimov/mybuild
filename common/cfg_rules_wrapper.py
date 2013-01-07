
import build_ctx
ctx = build_ctx

def TestFor(mod, test):
    pass

def lds_region(*args, **kargs):
    return ctx.cfg_rules.lds_region(*args, **kargs)

def lds_section_load(*args, **kargs):
    return ctx.cfg_rules.lds_section_load(*args, **kargs)

def lds_section(*args, **kargs):
    return ctx.cfg_rules.lds_section(*args, **kargs)

def include(*args, **kargs):
    return ctx.cfg_rules.include(*args, **kargs)

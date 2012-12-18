
def lds_region(name, base, size):
    pass

def lds_section_load(name, vma, lma):
    pass

def lds_section(name, reg):
    pass

def include(name, opts={}):
    import build_ctx
    build_ctx.constr.append((name, opts))

def exclude(name):
    pass

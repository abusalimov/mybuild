
import types

def method_pre_parse(ctx):
    ctx.root = types.ModuleType('root')
    return ctx

def method_decide_build(ctx):
    return ctx

def method_define_build(bld, model) :
    pass


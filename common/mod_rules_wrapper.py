
import build_ctx
ctx = build_ctx

# FIXME
from mybuild.pybuild.domain import *

def package(name):
    return ctx.mod_rules.package(name)

def module(name, *args, **kargs):
    return ctx.mod_rules.module(name, *args, **kargs)

def interface(name, *args, **kargs):
    return ctx.mod_rules.interface(name, *args, **kargs)

def library(name, *args, **kargs):
    return ctx.mod_rules.library(name, *args, **kargs)

def runlevel(n, depends=[]):
    return ctx.mod_rules.runlevel(n, depends)

def Integer(*args, **kargs):
    return ctx.mod_rules.Integer(*args, **kargs)

def Boolean(*args, **kargs):
    return ctx.mod_rules.Integer(*args, **kargs)

def List(*args, **kargs):
    return ctx.mod_rules.List(*args, **kargs)

def String(*args, **kargs):
    return ctx.mod_rules.String(*args, **kargs)

def IncludePath(*args, **kargs):
    return ctx.mod_rules.IncludePath(*args, **kargs)

def DefMacro(*args, **kargs):
    return ctx.mod_rules.DefMacro(*args, **kargs)

def Generated(*args, **kargs):
    return ctx.mod_rules.Generated(*args, **kargs)

def LDScript(*args, **kargs):
    return ctx.mod_rules.LDScript(*args, **kargs)

def InitFS(*args, **kargs):
    return ctx.mod_rules.InitFS(*args, **kargs)

def NoRuntime(*args, **kargs):
    return ctx.mod_rules.NoRuntime(*args, **kargs)

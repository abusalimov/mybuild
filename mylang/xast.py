"""Python ast extended.

Provides compatibility across different versions and simplified signatures.
"""

from _compat import *

from ast import *


try:
    XConst = NameConstant

except NameError:
    def XConst(const):
        return Name(repr(const), Load())


_const_mapping = {
    'None':  None,
    'False': False,
    'True':  True,
}

def XName(name, ctx=None):
    if name in _const_mapping:
        return XConst(_const_mapping[name])
    if ctx is None:
        ctx = Load()
    return Name(name, ctx)

def XCall(func, args=None, keywords=None, starargs=None, kwargs=None):
    return Call(func, args or [], keywords or [], starargs, kwargs)


if py3k:
    def xarg(name):
        return arg(name, None)

    try:
        def xarguments(args=None, vararg=None, kwarg=None, defaults=None):
            return arguments(args or [], vararg, [], [], kwarg,
                                 defaults or [])
        xarguments()

    except TypeError:
        # earlier versions of py3k have slightly different ast
        def xarguments(args=None, vararg=None, kwarg=None, defaults=None):
            if vararg is not None:
                varargarg = vararg.arg
                varargannotation = vararg.annotation
            else:
                varargarg = varargannotation = None
            if kwarg is not None:
                kwargarg = kwarg.arg
                kwargannotation = kwarg.annotation
            else:
                kwargarg = kwargannotation = None
            return arguments(args or [], varargarg, varargannotation,
                                 [], kwargarg, kwargannotation,
                                 defaults or [], [])

    def XFunctionDef(name, args, body, decos=None):
        return FunctionDef(name, args, body or [Pass()], decos or [],
                               None)

else:
    def xarg(name):
        return Name(name, Param())

    def xarguments(args=None, vararg=None, kwarg=None, defaults=None):
        return arguments(args or [], vararg, kwarg, defaults or [])

    def XFunctionDef(name, args, body, decos=None):
        return FunctionDef(name, args, body or [Pass()], decos or [])


try:
    Try

except NameError:
    def XTryExcept(body, handlers, orelse=None):
        return TryExcept(body, handlers, orelse or [Pass()])
else:
    def XTryExcept(body, handlers, orelse=None):
        return Try(body, handlers, orelse or [Pass()], [Pass()])


"""Python ast extended.

Provides compatibility across different versions and simplified signatures.
"""
from __future__ import absolute_import, division, print_function
from mybuild._compat import *

from ast import *


try:
    x_Const = NameConstant

except NameError:
    def x_Const(const):
        return Name(repr(const), Load())


_const_mapping = {
    'None':  None,
    'False': False,
    'True':  True,
}

def x_Name(name, ctx=None):
    if name in _const_mapping:
        return x_Const(_const_mapping[name])
    if ctx is None:
        ctx = Load()
    return Name(name, ctx)


try:
    def x_Call(func, args=None, keywords=None, starargs=None, kwargs=None):
        return Call(func, args or [], keywords or [], starargs, kwargs)
    x_Call(x_Const(None))
except TypeError:
    # Python 3.5 introduced generic handling of star- and kw-args in Call().
    def x_Call(func, args=None, keywords=None, starargs=None, kwargs=None):
        args = args or []
        keywords = keywords or []
        if starargs is not None:
            args.append(Starred(starargs, Load()))
        if kwargs is not None:
            keywords.append(keyword(None, kwargs))
        return Call(func, args, keywords)


if py3k:
    def x_arg(name):
        return arg(name, None)

    try:
        def x_arguments(args=None, vararg=None, kwarg=None, defaults=None):
            return arguments(args or [], vararg, [], [], kwarg,
                                 defaults or [])
        x_arguments()

    except TypeError:
        # earlier versions of py3k have slightly different ast
        def x_arguments(args=None, vararg=None, kwarg=None, defaults=None):
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

    def x_FunctionDef(name, args, body, decos=None):
        return FunctionDef(name, args, body or [Pass()], decos or [],
                               None)

else:
    def x_arg(name):
        return Name(name, Param())

    def x_arguments(args=None, vararg=None, kwarg=None, defaults=None):
        return arguments(args or [], vararg, kwarg, defaults or [])

    def x_FunctionDef(name, args, body, decos=None):
        return FunctionDef(name, args, body or [Pass()], decos or [])


try:
    Try

except NameError:
    def x_TryExcept(body, handlers, orelse=None):
        return TryExcept(body, handlers, orelse or [Pass()])
else:
    def x_TryExcept(body, handlers, orelse=None):
        return Try(body, handlers, orelse or [Pass()], [Pass()])

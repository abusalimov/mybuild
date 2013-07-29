"""
Exceptions for error handling.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-28"


import traceback as _traceback

from ...util.compat import *


class MyfileError(Exception):

    def print_error(self, tb=None):
        _traceback.print_exception(type(self), self, tb)


class ParseError(MyfileError):
    pass

class LinkageError(MyfileError):
    pass


class SyntaxErrorWloc(MyfileError, SyntaxError):

    def __init__(self, message, loc):
        super(SyntaxErrorWloc, self).__init__(message, loc.syntax_error_tuple)
        self.loc = loc

class Occurrence(SyntaxErrorWloc):

    def __init__(self, message, obj_wloc):
        _, loc = obj_wloc
        super(Occurrence, self).__init__(message, loc)


class CompoundError(MyfileError):

    def __init__(self, causes, message="Multiple errors"):
        super(CompoundError, self).__init__(message)
        self.causes = tuple(causes)

    def print_error(self, tb=None):
        super(CompoundError, self).print_error(tb)
        for cause in self.causes:
            cause.print_error()

    @classmethod
    def raise_if_any(cls, errors):
        errors = tuple(errors)

        if len(errors) == 1:
            raise errors[0]
        if len(errors) > 1:
            raise cls(errors)


class ArgAfterKwargError(CompoundError, ParseError):

    def __init__(self, kwarg_wloc, arg_wloc):
        kw, kw_arg_wloc = kwarg_wloc
        arg, loc = arg_wloc
        super(ArgAfterKwargError, self).__init__(
                (Occurrence("keyword arg '%s'" % kw, kw_arg_wloc),
                 Occurrence("non-keyword arg (%s)" % arg, arg_wloc)),
                "non-keyword arg after keyword arg")


class RepeatedKwargError(CompoundError, ParseError):

    def __init__(self, kw, first_arg_wloc, next_arg_wloc):
        super(RepeatedKwargError, self).__init__(
                (Occurrence("first", first_arg_wloc),
                 Occurrence("next",  next_arg_wloc)),
                "repeated keyword argument '%s'" % kw)


class UnresolvedNameError(LinkageError, SyntaxErrorWloc, NameError):

    def __init__(self, stub, name, loc):
        super(UnresolvedNameError, self).__init__(
                "name '{name}' is not defined: "
                "during resolving '{stub}' object".format(**locals()), loc)


class UnresolvedAttributeError(LinkageError, SyntaxErrorWloc, AttributeError):

    def __init__(self, stub, obj, attr, loc):
        obj_type = type(obj)
        super(UnresolvedAttributeError, self).__init__(
                "'{obj_type}' object ({obj}) has no attribute '{attr}': "
                "during resolving '{stub}' object".format(**locals()), loc)


class MultipleDefinitionsError(CompoundError, LinkageError, NameError):

    def __init__(self, name, stubs):
        super(MultipleDefinitionsError, self).__init__(
                (Occurrence("defined as '%s'" % stub, stub.name_wloc)
                 for stub in stubs),
                "Multiple objects defined for name '%s'" % name)

        self.name = name
        self.stubs = stubs


class ReferenceLoopError(CompoundError, LinkageError, TypeError):

    def __init__(self, chain_init, chain_wlocs):
        super(ReferenceLoopError, self).__init__(
                (Occurrence("referenced from '%s'" % stub_wloc[0], stub_wloc)
                 for stub_wloc in chain_wlocs),
                "%s object references itself (eventually)" % chain_init)


class InstantiationError(LinkageError, SyntaxErrorWloc, TypeError):

    def __init__(self, exc, stub):
        _, loc = stub.type_root_wloc
        super(InstantiationError, self).__init__(
                "{exc.message}: during creation of '{stub}' object"
                    .format(**locals()), loc)


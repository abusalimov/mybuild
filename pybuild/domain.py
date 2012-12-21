
from exception import *

import itertools 

class Domain(frozenset):
    
    def value(self):
        if len(self) > 1:
            raise MultiValueException(self)
        elif len(self) < 1:
            raise CutConflictException(self)
        return self.force_value()

    def force_value(self):
        for v in sorted(self):
            return v

    @classmethod
    def single_value(cls, value):
        return cls([value])

    def __or__(self, other):
        return self.__class__(itertools.chain(self, other))

class ListDom():
    def __init__(self, it):
        self.it = tuple(it)

    def __nonzero__(self):
        return True

    def value(self):
        return self.force_value()

    def force_value(self):
        return tuple(self.it)

    def __and__(self, other):
        return other

    def __len__(self):
        return 1

    def __add__(self, other):
        self.it = self.it + tuple(other)
        return self

    def __iter__(self):
        return [self.it].__iter__()

    @classmethod
    def single_value(cls, value):
        return cls(value) 

    def __repr__(self):
        return '<ListDom: %s' % (self.it,)

class IntegerDom(Domain):
    def __repr__(self):
        return '<IntegerDom: [%d-%d]' % (min(self), max(self))

    def __str__(self):
        return '<IntegerDom: [%d-%d]' % (min(self), max(self))

class ModDom(Domain):
    def __init__(self, init_iter, default_impl = None):

        self.default_impl = default_impl

        Domain.__init__(self, init_iter)

    def __and__(self, other):
        if isinstance(other, BoolDom):
            if True in other:
                md = self - ModDom([self.default_impl])
            if False in other:
                md = ModDom(self, default_impl)
        else:
            md = Domain.__and__(self, other)
            md.default_impl = self.default_impl

        return md

    def __sub__(self, other):
        md = Domain.__sub__(self, other)
        md.default_impl = self.default_impl
        return md

    def __or__(self, other):
        return self.__class__(itertools.chain(self, other), default_impl = self.default_impl)

class BoolDom(Domain):
    pass



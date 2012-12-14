
import operator

from exception import *

class Inherit():
    def __init__(self, super=None):
	self.super = super

    def supers(self):
	if self.super:
	    return [self.super] + self.super.supers()
	return []

class BaseScope(dict):
    def __init__(self, parent=None):
	self.parent = parent
	
    def __getitem__(self, x):
	if dict.has_key(self, x):
	    return dict.__getitem__(self, x)
	elif self.parent:
	    return self.parent[x]
	else:
	    raise AttributeError

    def __len__(self):
	par = 0
	if self.parent:
	    par = len(self.parent)
	return dict.__len__(self) + par

    def keys(self):
	par_keys = set()
	if self.parent: 
	    par_keys = set(self.parent.keys())

	return set(dict.keys(self)) | par_keys

    def items(self):
	return ((k, self[k]) for k in self.keys())

    def has_key(self, k):
	return k in self.keys()

    def __nonzero__(self):
	return True

class Scope(BaseScope):
    def value(self, opt):
	d = self[opt]
	if len(d) > 1:
	    raise MultiValueException(opt)
	elif len(d) < 1:
	    raise CutConflictException(opt)
	return d.force_value()

    def __repr__(self):
	return 'Scope {' + \
	    reduce (operator.add, map(lambda x: "\t%s: %s" % x, self.items()), "")


import os
import re

from annotation import *

class Source(object):
    def __init__(self, dirname, filename):
	self.dirname = dirname
	self.filename = filename

    def __repr__(self):
	return "Source('%s/%s')" % (self.dirname, self.filename)

    def fullpath(self):
	return os.path.join(self.dirname, self.filename)

    def annotations(self):
	anns = getattr(self.filename, 'annots', [])
	return anns

    def build(self, bld, opt, scope):
	f = self.fullpath()
	cnt = 0
	for ann in self.annotations():
	    f = ann.build(bld, f, opt, scope)
	if re.match('.*\.c', f):	
	    return self.build_rule(f, bld, opt, scope)
	    
	return f

    def build_rule(self, src, bld, opt, scope):
	tgt = src.replace('.c', '.o')
	bld.objects(
	    name = tgt,
	    source = src,
	    defines = ['__EMBUILD_MOD__'],
	    includes = bld.env.includes,
	)
	return tgt

class StaticSource(Source):
    def build_rule(self, src, bld, opt, scope):
	tgt = src.replace('.c', '.a')
	bld.stlib(
	    name = tgt,
	    source = src,
	    target = tgt,
	    defines = ['__EMBUILD_MOD__'],
	    includes = bld.env.includes,
	)
	return tgt






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
	for ann in self.annotations():
	    f = ann.build(bld, f, opt, scope)

	return self.build_rule(f, bld, opt, scope)

    def build_rule(self, src, bld, opt, scope):
	return src
	#if not re.match('.*\.[cS]', src):
	    #return src
	#print src
	#tgt = "%s.o" % (src,)
	#bld(
	    #features = 'c', 
	    #source = src,
	    #target = tgt,
	    #defines = ['__EMBUILD_MOD__'],
	    #includes = bld.env.includes,
	#)
	#return tgt 

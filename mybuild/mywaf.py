"""
Mybuild tool for Waf.
"""

from waflib import Context as wafcontext
from waflib import Utils   as wafutils

def options(ctx):
	print('mywaf: %r' % ctx)

def configure(ctx):
	print('mywaf: %r' % ctx)

def load_myfiles(ctx, myfile_names, root_node=None):
	if root_node is None:
		root_node = ctx.path
	myfiles_glob = ['**/' + f for f in wafutils.to_list(myfile_names)]
	files = root_node.ant_glob(myfiles_glob)
	print files

wafcontext.Context.load_myfiles = load_myfiles

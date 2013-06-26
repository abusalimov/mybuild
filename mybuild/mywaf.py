"""
Mybuild tool for Waf.
"""

from waflib import Context as wafcontext

def options(ctx):
	print('mywaf: %r' % ctx)

def configure(ctx):
	print('mywaf: %r' % ctx)

def load_myfiles(ctx, files, package_root):
	pass

wafcontext.Context.load_myfiles = load_myfiles

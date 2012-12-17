
import sys
import os
import re

sys.path.append(os.getcwd())

from package   import Package, obj_in_pkg
from scope     import Scope
from ops       import add_many, cut_many, cut, fixate

from option    import Boolean, List, Integer, String
from domain    import BoolDom, ListDom, IntegerDom, Domain, ModDom

from module    import Module
from interface import Interface

from parser.mod_rules import *
from parser.cfg_rules import *

import mybuild.parser

from waflib.TaskGen import feature, after
from waflib import TaskGen, Task
from waflib import Utils

@TaskGen.extension('.lds.S')
def lds_s_hook(self, node):
    tgtnode = node.change_ext('.lds', '.lds.S')
    self.env['DEFINES'] = self.defines
    return self.create_task('lds_s', node, tgtnode)

class lds_s(Task.Task):
    run_str = '${CC} ${ARCH_ST:ARCH} ${CFLAGS} ${CPPFLAGS} ${FRAMEWORKPATH_ST:FRAMEWORKPATH} ${CPPPATH_ST:INCPATHS} ${DEFINES_ST:DEFINES} ${CC_SRC_F}${SRC} -E -P -o ${TGT}'
    ext_out = ['.lds'] # set the build order easily by using ext_out=['.h']

@feature('module_header')
def header_gen(self):
    header = '''
#ifndef {GUARD}
#define {GUARD}

{INCLUDES}

{OPTIONS}

#endif /* {GUARD} */
'''
    options = []
    for name, opt in self.mod.items():
	repr = ''
	if isinstance(opt, Integer):
	    repr = 'NUMBER'
	elif isinstance(opt, Boolean):
	    repr = 'BOOLEAN'
	elif isinstance(opt, String):
	    repr = 'STRING'
	else:
	   continue

	options.append('OPTION_%s_%s %s' % (repr, opt.qualified_name().replace('.', '__'),
	    self.scope[opt].value()))

    includes = []
    
    if isinstance(self.mod, Interface):
	for impl in self.scope[self.mod]:
	    for src in impl.sources:
		if re.match('.*\.h', src.filename):
		    includes.append(src.fullpath())

    hdr = header.format(GUARD=self.mod.qualified_name().replace('.', '_').upper(),
	OPTIONS=''.join(map(lambda str: '#define %s\n\n' %(str,), options)),
	INCLUDES=''.join(map(lambda str: '#include __impl_x(%s)\n\n' % (str,), includes)))

    self.rule = lambda self: self.outputs[0].write(hdr)

def waf_layer(bld):

    scope = Scope()

    ctx = mybuild.parser.parse(['src'], 'pyconf')

    modlst = map(lambda name: ctx.root[name], ctx.modlist)
    add_many(scope, modlst)

    modconstr = map(lambda (name, dom): (ctx.root[name], dom), ctx.modconstr)

    cut_scope = cut_many(scope, modconstr)
    final = fixate(cut_scope)

    bld.env.ld_defs = ctx.ld_defs

    for opt, dom in final.items():
	need_header = isinstance(opt, Interface)

	if (isinstance(opt, Module) and dom == Domain([True])):
	    need_header |= True

	    for src in opt.sources:
		src.build(bld, opt, final) 

	if need_header:
	    bld(features = 'module_header',
		target = 'include/module/%s.h' % (opt.qualified_name().replace('.','/'),),
		mod = opt,
		scope = final)


    bld(
	features = 'c cprogram',
	target = bld.env.target,
	includes = bld.env.includes,
	linkflags = bld.env.LDFLAGS,
	use = 'generated objects ldscripts',
    )

if __name__ == '__main__':
    import sys
    mybuild_main(sys.argv[1:])

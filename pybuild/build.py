
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

def lds_region(name, base, size):
    global __ld_defs
    __ld_defs.append('LDS_REGION_BASE_%s=%s' % (name, base))
    __ld_defs.append('LDS_REGION_SIZE_%s=%s' % (name, size))

def lds_section_load(name, vma, lma):
    global __ld_defs
    __ld_defs.append('LDS_SECTION_VMA_%s=%s' % (name, vma))
    __ld_defs.append('LDS_SECTION_LMA_%s=%s' % (name, lma))

def lds_section(name, reg):
    lds_section_load(name, reg, reg)


def mybuild_main(argv):
    import os
    rootpkg = Package('root', None)
    allmodlist = []
    scope = Scope()

    glob = globals()

    glob['__package_tree'] = rootpkg
    glob['__modlist'] = allmodlist

    for arg in argv:
	for dirpath, dirnames, filenames in os.walk(arg):
	    for file in filenames:
		if file.endswith('.py') or file == 'Pybuild':
		    glob['__dirname'] = dirpath
		    execfile(os.path.join(dirpath, file), glob)

    #print rootpkg
    #print
    #print glob['__modlist']

    conf = 'pyconf/conf.py'

    glob['__scope'] = scope

    modlst = map(lambda name: glob['__package_tree'][name], glob['__modlist'])
    #print 
    #print modlst
    add_many(scope, modlst)

    glob['__modconstr'] = []

    execfile(conf, glob)

    modconstr = map(lambda (name, dom): (rootpkg[name], dom), glob['__modconstr'])

    #print 
    #print modconstr

    cut_scope = cut_many(scope, modconstr)
    final = fixate(cut_scope)
    #print
    #print final

    return final

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

    final = mybuild_main(['src'])   

    lds_conf = 'pyconf/lds.py'

    glob = globals()

    glob['__ld_defs'] = []

    execfile(lds_conf, glob)

    bld.env._ld_defs = glob['__ld_defs']

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

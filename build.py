
import sys
import os
import re

sys.path.append(os.getcwd())

import parser

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

def inchdr(type, mod_name, opt_name, val):
    return 'OPTION_%s_%s__%s %s' % (type, mod_name.replace('.', '__'), opt_name, val)

@feature('module_header')
def header_gen(self):
    header = '''
#ifndef {GUARD}
#define {GUARD}

{INCLUDES}

{OPTIONS}

#endif /* {GUARD} */
'''
    hdr = header.format(GUARD=self.mod_name.replace('.', '_').upper(),
	OPTIONS=''.join(map(lambda str: '#define %s\n\n' %(str,), self.header_opts)),
	INCLUDES=''.join(map(lambda str: '#include __impl_x(%s)\n\n' % (str,), self.header_inc)))

    self.target = 'include/module/%s.h' % (self.mod_name.replace('.','/'),)
    self.rule = lambda self: self.outputs[0].write(hdr)

def waf_layer(bld):

    ctx = parser.BuildCtx()

    ctx.bld = bld

    if bld.env.METHOD == 'A':
	from pybuild.method import method_pre_parse, method_define_build, method_decide_build
    elif bld.env.METHOD == 'E':
	from mybuild.method import method_pre_parse, method_define_build, method_decide_build
    else:
	raise Exception("Unknown method '%s'" % (bld.env.METHOD, ))

    ctx = method_pre_parse(ctx)

    ctx = parser.parse(ctx, ['src'], 'pyconf', bld.env.METHOD)

    model = method_decide_build(ctx)

    method_define_build(bld, model)

    bld(
	features = 'c cprogram',
	target = bld.env.target,
	includes = bld.env.includes,
	linkflags = bld.env.LDFLAGS,
	use = 'generated objects ldscripts',
    )


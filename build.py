
import sys
import os
import re

sys.path.append(os.getcwd())

import parser

def inchdr(type, mod_name, opt_name, val):
    return 'OPTION_%s_%s__%s %s' % (type, mod_name.replace('.', '__'), opt_name, val)

def waf_entry(bld):

    ctx = bld.env

    if bld.env.METHOD == 'A':
	from pybuild.method import method_pre_parse, method_define_build, method_decide_build
    elif bld.env.METHOD == 'E':
	from mybuild.method import method_pre_parse, method_define_build, method_decide_build
    else:
	raise Exception("Unknown method '%s'" % (bld.env.METHOD, ))

    ctx = method_pre_parse(ctx)

    ctx = parser.parse(ctx, ['src', 'pyconf'], bld.env.METHOD)

    model = method_decide_build(ctx)

    bld.out = []

    method_define_build(bld, model)

    bld(
	features = 'c cprogram',
	target = bld.env.target,
	includes = bld.env.includes,
	linkflags = bld.env.LDFLAGS,
	use = ['generated', 'ldscripts'] + bld.out,
    )


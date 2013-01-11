
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

    ctx = parser.parse(ctx, ['src', 'third-party', 'pyconf'], bld.env.METHOD)

    model = method_decide_build(ctx)

    bld.out = []

    ctx.model = model 
    ctx.bld   = bld

    method_define_build(ctx)

    bld(
        features = 'c ld',
        target = 'image_nosymbols.o',
        includes = bld.env.includes,
        linkflags = ['--relocatable'] + ctx.system_LDFLAGS + ctx.user_LDFLAGS, 
        use = ['generated', 'ldscripts'] + bld.out,
    )

    bld(
        rule='nm -n ${SRC[1]} | awk -f ../mk/script/${SRC[0]} > ${TGT}',
        source = ['mk/script/nm2c.awk', bld.path.get_bld().make_node('image_nosymbols.o')],
        target = 'symbols_pass1.c'
    )

    bld(
        features = 'c cstlib',
        source = 'symbols_pass1.c',
        target = 'symbols_pass1.o',
        includes = bld.env.includes,
    )

    bld(
        features = 'c ld',
        source = bld.path.get_bld().find_or_declare('image_nosymbols.o'),
        linkflags = ['--relax' ] + ctx.system_LDFLAGS + ctx.user_LDFLAGS + ['-T%s' % ctx.linker_script[0]],
        use = 'symbols_pass1.o',
        target = 'image_pass1.o'
    )

    bld(
        rule='nm -n ${SRC[1]} | awk -f ../mk/script/${SRC[0]} > ${TGT}',
        source = ['mk/script/nm2c.awk', bld.path.get_bld().make_node('image_pass1.o')],
        target = 'symbols_pass2.c'
    )

    bld(
        features = 'c cstlib',
        source = 'symbols_pass2.c',
        target = 'symbols_pass2.o',
        includes = bld.env.includes,
    )

    bld(
        features = 'c ld',
        source = bld.path.get_bld().find_or_declare('image_pass1.o'),
        linkflags = ['--relax' ] + ctx.system_LDFLAGS + ctx.user_LDFLAGS + ['-T%s' % ctx.linker_script[0]],
        use = 'symbols_pass2.o',
        target = 'embox'
    )

        


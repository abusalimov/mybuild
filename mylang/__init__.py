"""
Parser, compiler and runtime support for My-files.
"""
from __future__ import absolute_import


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


from _compat import *

try:
    from mylang.parse import parse
except ImportError:
    def parse(*args, **kwargs):
        raise ImportError('PLY is not installed')


def my_compile(source, filename='<unknown>', mode='exec'):
    ast_root = parse(source, filename, mode)
    return compile(ast_root, filename, mode)


if __name__ == "__main__":
    source = '''

    kernel :: module(debug = False) {
        "Docstring!"

        source: "init.c",

        depends: [
            embox.arch.cpu(endian="be"){runtime: False},

            embox.driver.diag.diag_api,
        ],
        depends: embox.kernel.stack,

    };

    '''
    from mylang import runtime
    from util.misc import singleton
    from pprint import pprint

    def get_globals():
        @singleton
        class embox(object):
            __my_prepare_obj__ = None
            def __call__(self, *args, **kwargs):
                print self, args, kwargs
                return self
            def __getattr__(self, attr):
                return self

        class module(object):
            def __init__(self, *args, **kwargs):
                super(module, self).__init__()
                print self, args, kwargs
            def __call__(self, *args, **kwargs):
                print self, args, kwargs
                return self

        __builtins__ = runtime.prepare_builtins()
        return locals()

    try:
        code = my_compile(source)
        exec(code, dict(globals(), **get_globals()))

    except:
        import sys, traceback, code
        tb = sys.exc_info()[2]
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)



"""
Parser, compiler and runtime support for My-files.
"""
from __future__ import absolute_import


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


from _compat import *


def my_compile(source, filename='<unknown>', mode='exec'):
    try:
        from mylang.parse import parse
    except ImportError:
        raise ImportError('PLY is not installed')

    ast_root = parse(source, filename, mode)
    return compile(ast_root, filename, mode)


if __name__ == "__main__":
    source = '''

    kernel :: module(debug = False) {
        "Docstring!"

        source: "init.c",

        depends: [
            embox.arch.cpu(endian="be").{runtime: False},

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
            def __call__(self, *args, **kwargs):
                print(self, args, kwargs)
                return self
            def __getattr__(self, attr):
                return self

        class module(object):
            def __init__(self, *args, **kwargs):
                super(module, self).__init__()
                print(self, args, kwargs)
            def __call__(self, *args, **kwargs):
                print(self, args, kwargs)
                return self
            def __my_new__(self, init_func):
                print(self, init_func)
                return init_func(self)

        __builtins__ = runtime.builtins
        return locals()

    try:
        code = my_compile(source)
        ns = dict(globals(), **get_globals())
        exec(code, ns)

        print(ns['kernel'].source)

    except:
        import sys, traceback, code
        tb = sys.exc_info()[2]
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)



"""
Parser/linker for My-files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


from _compat import *

from mylang.linkage import Linker
from mylang.errors import MyfileError
try:
    from mylang.parse import parse
except ImportError:
    parse = None


def load(linker, source, filename=None, builtins={}):
    if parse is None:
        raise ImportError('PLY is not installed')

    return parse(linker, source, filename, builtins)


if __name__ == "__main__":
    source = '''//module Kernel,

    //obj obj,
    foo bar,
    module foo(xxx=bar),

    module Kernel(debug = False) {
        "Docstring!"

        x: xxx xname() {},

        source: "init.c",

        depends: [
            embox.arch.cpu(endian="be"){runtime: False},

            embox.driver.diag.diag_api,
        ],
        depends: embox.kernel.stack,

    },


    '''
    from util.misc import singleton

    from pprint import pprint

    def get_builtins():
        @singleton
        class embox(object):
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
        xxx = lambda: 42

        return dict(locals(), **{
                        'None':  lambda: None,
                        'True':  lambda: True,
                        'False': lambda: False,
                    })

    linker = Linker()
    try:
        pprint(load(linker, source, builtins=get_builtins()))
        linker.link_global()

    except MyfileError as e:
        e.print_error()

    except:
        import sys, traceback, code
        tb = sys.exc_info()[2]
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        code.interact(local=ns)



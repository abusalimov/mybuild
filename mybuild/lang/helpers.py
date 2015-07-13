"""
Helpers for defining grammar rules for PLY Yacc.
"""

from mybuild._compat import *

import functools
import inspect


def _rule_indices_from_argspec(func, with_p=True):
    args, _, _, defaults = inspect.getargspec(inspect.unwrap(func))
    nr_args = len(args)
    defaults = list(defaults) if defaults is not None else []

    if with_p:
        if not nr_args:
            raise TypeError("need at least 'p' argument")
        if len(defaults) == nr_args:
            defaults = defaults[1:]
        nr_args -= 1

    if None in defaults:
        def_nones = defaults[defaults.index(None):]
        if def_nones.count(None) != len(def_nones):
            raise TypeError("index argument after 'None'")

        def_indices = defaults[:-len(def_nones)]
    else:
        def_indices = defaults

    return list(range(1, nr_args-len(defaults)+1)) + def_indices

def _symbol_at(p, idx):
    return p[idx + (idx < 0 and len(p))]
def _symbols_at(p, indices):
    return [_symbol_at(p, idx) for idx in indices]


def rule(func):
    indices = _rule_indices_from_argspec(func)
    @functools.wraps(func)
    def decorated(p):
        p[0] = func(p, *_symbols_at(p, indices))
    return decorated


from functools import partial

from exception import *

from scope import Scope

debug_out = True

def add_many(scope, ents):
    for ent in ents:
        scope[ent] = ent.domain
        if hasattr(ent,'items'):
            for name, opt in ent.items():
                scope[opt] = opt.domain

    for ent in ents:
        scope = ent.add_trigger(scope)
        if hasattr(ent,'items'):
            for name, opt in ent.items():
                scope = opt.add_trigger(scope)
    
    for k, v in scope.items():
        if not v:
            raise CutConflictException(k)

    return scope

def incut_cont(cont, scope, opt, domain):
    if debug_out:
        print 'cut %s for %s' % (opt, domain)
    strict_domain = scope[opt] & domain
    old_domain = scope[opt]
    if strict_domain:
        if debug_out:
            print 'cut %s is now %s' % (opt, strict_domain)
        differ = strict_domain != old_domain
        scope[opt] = strict_domain
        if differ:
            scope = opt.cut_trigger(cont, scope, old_domain)
        if debug_out:
            print 'OK %s for %s' % (opt, domain)
    else:
        if debug_out:
            print 'FAIL %s for %s' % (opt, domain)
        raise CutConflictException(opt)

    return cont(scope)

def incut(scope, opt, domain):
    return incut_cont(lambda x: x, scope, opt, domain)

def cut_iter(scope, opts):
    if not opts:
        return scope

    opt, domain = opts[0]
    return incut_cont(partial(cut_iter,opts=opts[1:]), scope, opt, domain)

def cut(scope, opt, domain):

    scope = Scope(scope)

    scope = incut(scope, opt, domain)

    return scope

def cut_many(scope, opts):
    has_no_trigger = filter(lambda m: not getattr(m, 'include_trigger', False), 
                    [m for m, d in opts])
    d = dict(opts)

    for opt in has_no_trigger:
        scope = incut(scope, opt, d[opt])
        del d[opt]

    return cut_iter(scope, [(opt, dom) for opt, dom in d.items()])

def fix(scope, opt):
    if debug_out:
        print 'fixing %s within %s' %(opt, scope[opt])
    return opt.fix_trigger(scope)

def fixate(scope):
    scope = Scope(scope)

    for opt, domain in scope.items():
        scope = fix(scope, opt)

    return scope


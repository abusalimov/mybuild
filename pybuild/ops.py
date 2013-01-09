
from functools import partial

from exception import *

from scope import Scope

import logging

#logging.basicConfig(level=logging.DEBUG)

def add_many(scope, ents):
    for ent in ents:
        scope[ent] = ent.domain
        if hasattr(ent,'items'):
            for name, opt in ent.contents():
                scope[opt] = opt.domain

    for ent in ents:
        scope = ent.add_trigger(scope)
        if hasattr(ent,'items'):
            for name, opt in ent.contents():
                scope = opt.add_trigger(scope)
    
    for k, v in scope.items():
        if not v:
            raise CutConflictException(k, scope)

    return scope

def incut_cont(cont, scope, opt, domain):
    logging.debug('cut %s for %s' % (opt, domain))
    strict_domain = scope[opt] & domain
    old_domain = scope[opt]
    logging.debug('cut %s is old domain' % (old_domain))
    if strict_domain:
        logging.debug('cut %s is now %s' % (opt, strict_domain))
        differ = strict_domain != old_domain
        scope[opt] = strict_domain
        if differ:
            scope = opt.cut_trigger(cont, scope, old_domain)
        logging.debug('OK %s for %s' % (opt, domain))
    else:
        logging.debug('FAIL %s for %s' % (opt, domain))
        raise CutConflictException(opt, scope)

    return cont(scope)

def incut(scope, opt, dom):
    post = scope.post_list
    if getattr(opt, 'include_trigger', False) and post != None:
        post.append((opt, dom))
        return scope
    return incut_cont(lambda x: x, scope, opt, dom)

def cut(scope, opt, domain):

    scope = Scope(scope)

    scope = incut(scope, opt, domain)

    return scope

def cut_iter(scope, opts):
    if not opts:
        return scope

    opt, domain = opts[0]
    return incut_cont(partial(cut_iter,opts=opts[1:]), scope, opt, domain)

def cut_many(scope, opts):
    
    for opt, dom in opts:
        scope = incut(scope, opt, dom)

    return scope 

def cut_many_fancy(scope, find_fn, constr):
    return cut_many(scope, [(find_fn(name), find_fn(name).domain_class(val)) for name, val in constr])

def fix(scope, opt, *args, **kargs):
    logging.debug('fixing %s within %s' %(opt, scope[opt]))
    ret = opt.fix_trigger(scope, *args, **kargs)
    logging.debug('fixed %s with %s' %(opt, ret[opt]))

    return ret

def fixate(scope):
    scope = Scope(scope)

    post = scope.post_list

    scope.post_list = None

    scope = cut_iter(scope, post)

    for opt, domain in scope.items():
            scope = fix(scope, opt)

    return scope


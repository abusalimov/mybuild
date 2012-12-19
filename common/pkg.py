
def modlist(pkg, pkg_cls, mod_cls, content_fn):
    def find_mods(pkg, lst, pkg_nm):
        for name, obj in content_fn(pkg):
            if isinstance(obj, pkg_cls):
                find_mods(obj, lst, '%s.%s' % (pkg_nm, name))
            elif isinstance(obj, mod_cls):
                lst.append('%s.%s = %s' % (pkg_nm, name, obj.canon_repr()))
    
    ans = []
    find_mods(pkg, ans, '')

    return sorted(ans)

    

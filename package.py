
def pkg_rec(self, attr):
    splt = attr.split('.', 1)
    if self.dict.has_key(splt[0]):
        obj = self.dict[splt[0]]
    else:
        raise AttributeError(attr)

    if len(splt) > 1:
        return getattr(obj, splt[1])

    return obj

class Package():
    def __init__(self, name, pkg=None):
        self.name = name
        self.pkg  = pkg
        self.hash = hash(self.qualified_name())
        self.dict = {}

    def __getitem__(self, key):
        raise Exception

    def __getattr__(self, attr):
        return pkg_rec(self, attr)

    def set(self, name, obj):
        self.dict[name] = obj

    def build_subpack(self, key):
        splt = key.split('.', 1)
    
        if not self.dict.has_key(splt[0]):
            self.dict[splt[0]] = Package(splt[0], self)

        if len(splt) > 1:
            return self.dict[splt[0]].build_subpack(splt[1])

        return self.dict[splt[0]]

    def qualified_name(self):
        if self.pkg == None:
            return ""
        parent = self.pkg.qualified_name()
        if parent:
                return '%s.%s' % (parent, self.name)
        return self.name

    def root(self):
        if self.pkg == None:
            return self
        return self.pkg.root()

    def find_with_imports(self, imports, name):
        for impt in imports:
            if impt:
                pkg = getattr(self, impt)
            else:
                pkg = self

            try:
                return getattr(pkg, name)
            except AttributeError:
                pass
        raise AttributeError(name)

    def __hash__(self):
        return self.hash
    
    def __str__(self):
        return '<Package %s: %s>' % (self.name, self.dict)

def obj_in_pkg(cls, package, name, *args, **kargs): 
    kargs['pkg'] = package
    ret = cls(name, *args, **kargs)
    package.set(name, ret)
    return ret



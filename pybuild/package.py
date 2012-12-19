
class Package(dict):
    def __init__(self, name, pkg=None):
        self.name = name
        self.pkg = pkg  
        self.hash = hash(self.qualified_name())

    def __getitem__(self, key):
        splt = key.split('.', 1)
        obj = dict.__getitem__(self, splt[0])

        if len(splt) > 1:
            return obj[splt[1]]

        return obj

    def built_subpack(self, key):
        splt = key.split('.', 1)
        obj = self

        if not self.has_key(splt[0]):
            dict.__setitem__(self, splt[0], Package(splt[0], self))

        if len(splt) > 1:
            return self[splt[0]].built_subpack(splt[1])

        return self

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
                pkg = self[impt]
            else:
                pkg = self

            try:
                return pkg[name]
            except KeyError:
                pass
        raise KeyError(name)

    def __hash__(self):
        return self.hash

def obj_in_pkg(cls, package, name, *args, **kargs): 
    kargs['pkg'] = package
    package[name] = cls(name, *args, **kargs)



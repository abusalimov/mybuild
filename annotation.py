
class Annotation():
    def __init__(self):
        pass

class NoRuntimeAnnotation(Annotation):
    pass

class SourceAnnotation(Annotation):
    pass

class LDScriptAnnotation(SourceAnnotation):
    def build(self, bld, spec, mod, scope):
        source = spec.src
        tgt = source.replace('.lds.S', '.lds')
        bld.env.append_value('LINKFLAGS', '-Wl,-T,%s' % (tgt,))
        bld(
            name = 'ldscripts',
            features = 'includes',
            source = source,
            includes = bld.env.includes,
            defines = bld.env.ld_defs,
        )
        spec.src = tgt
        return spec

class GeneratedAnnotation(SourceAnnotation):
    def __init__(self, rule):
        self.rule = rule
    def build(self, bld, spec, mod, scope):
        bld(
            rule = lambda f: f.outputs[0].write(self.rule(mod, scope)),
            target = spec.src
        )
        return spec 

class DefMacroAnnotation(Annotation):
    def __init__(self, defines):
        self.defines = defines
    def build(self, bld, spec, mod, scope):
        spec.defines += self.defines
        return spec

def annotated(obj, annot):
    try:
        obj.annots.append(annot)
        return obj
    except Exception, ex:
        class AnnotHolder(obj.__class__):
            pass
        new_obj = AnnotHolder(obj)
        new_obj.annots = [annot]
        return new_obj

def NoRuntime(obj):
    return annotated(obj, NoRuntimeAnnotation())

def LDScript(obj):
    return annotated(obj, LDScriptAnnotation())

def Generated(obj, rule):
    return annotated(obj, GeneratedAnnotation(rule))

def DefMacro(defines, obj):
    return annotated(obj, DefMacroAnnotation(defines))

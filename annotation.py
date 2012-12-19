
class Annotation():
    def __init__(self):
        pass

class NoRuntimeAnnotation(Annotation):
    pass

class SourceAnnotation(Annotation):
    pass

class LDScriptAnnotation(SourceAnnotation):
    def build(self, ctx, spec, mod):
        source = spec.src
        tgt = source.replace('.lds.S', '.lds')
        ctx.bld.env.append_value('LINKFLAGS', '-Wl,-T,%s' % (tgt,))
        ctx.bld(
            name = 'ldscripts',
            features = 'includes',
            source = source,
            includes = ctx.bld.env.includes,
            defines = ctx.bld.env.ld_defs,
        )
        spec.src = tgt
        return spec

class GeneratedAnnotation(SourceAnnotation):
    def __init__(self, rule):
        self.rule = rule
    def build(self, ctx, spec, mod):
        ctx.bld(
            rule = lambda f: f.outputs[0].write(self.rule(spec.src, mod, ctx)),
            target = spec.src
        )
        return spec 

class DefMacroAnnotation(Annotation):
    def __init__(self, defines):
        self.defines = defines
    def build(self, ctx, spec, mod):
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
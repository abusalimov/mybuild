
from pybuild.util import isvector

class Annotation():
    def __init__(self):
        pass

    def get_name(self):
        return self.__class__.__name__

    def listify(self, maybe_list):
        if not isinstance(maybe_list, tuple) and not isinstance(maybe_list, list):
            return [maybe_list]
        return maybe_list

    def build(self, ctx, spec, mod):
        return spec

class NoRuntimeAnnotation(Annotation):
    pass

class SourceAnnotation(Annotation):
    pass

class InitFSAnnotation(Annotation):
    pass

class LDScriptAnnotation(SourceAnnotation):
    def build(self, ctx, spec, mod):
        source = spec.src
        tgt = source.replace('.lds.S', '.lds')
        ctx.bld.env.append_value('linker_script', tgt)
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
        rule = self.rule(spec.src, mod, ctx)
        ctx.bld(
            rule = lambda f: f.outputs[0].write(rule),
            target = spec.src
        )
        return spec 

class DefMacroAnnotation(Annotation):
    def __init__(self, defines):
        self.defines = self.listify(defines)

    def build(self, ctx, spec, mod):
        spec.defines += self.defines
        return spec

class IncludePathAnnotation(Annotation):
    def __init__(self, paths):
        self.paths = self.listify(paths)

    def build(self, ctx, spec, mod):
        spec.includes += self.paths
        return spec

def annotated(obj, annot):
    def annotated_obj(obj, annot):
        try:
            obj.annots.append(annot)
            return obj
        except Exception, ex:
            class AnnotHolder(obj.__class__):
                pass
            new_obj = AnnotHolder(obj)
            new_obj.annots = [annot]
            return new_obj

    if isvector(obj):
        return [annotated_obj(obj, annot) for obj in obj]
    return annotated_obj(obj, annot)

def NoRuntime(obj):
    return annotated(obj, NoRuntimeAnnotation())

def LDScript(obj):
    return annotated(obj, LDScriptAnnotation())

def InitFS(obj):
    return annotated(obj, InitFSAnnotation())

def Generated(obj, rule):
    return annotated(obj, GeneratedAnnotation(rule))

def DefMacro(defines, obj):
    return annotated(obj, DefMacroAnnotation(defines))

def IncludePath(paths, obj):
    return annotated(obj, IncludePathAnnotation(paths))



class Annotation():
    def __init__(self):
	pass

class NoRuntimeAnnotation(Annotation):
    pass

class SourceAnnotation(Annotation):
    pass

class LDScriptAnnotation(SourceAnnotation):
    def build(self, bld, source, mod, scope):
	tgt = source.replace('.lds.S', '.lds')
	bld.env.append_value('LINKFLAGS', '-Wl,-T,%s' % (tgt,))
	bld(
	    name = 'ldscripts',
	    features = 'includes',
	    source = source,
	    includes = bld.env.includes,
	    defines = bld.env.ld_defs,
	)
	return tgt

class GeneratedAnnotation(SourceAnnotation):
    def __init__(self, rule):
	self.rule = rule
    def build(self, bld, source, mod, scope):
	tgt = source
	bld(
	    rule = lambda f: f.outputs[0].write(self.rule(mod, scope)),
	    target = tgt
	)
	return tgt

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

def DefMacro(define, obj):
    return obj

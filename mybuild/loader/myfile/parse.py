import ply.yacc

from . import lex

# Get the token map
tokens = lex.tokens

p_cnt = 0
def p(rule, fxn=None):
    if fxn is None:
        def fxn(p): pass

    global p_cnt
    p_cnt += 1

    fxn.__name__ = 'p_rule_%d' % p_cnt
    fxn.__doc__  = rule

    globals[fxn.__name__] = fxn

def p0(fxn):
    if isinstance(fxn, int):
        fxn = itemgetter(fxn)
    def ret(p):
        p[0] = fxn()
    return ret

def append(item_idx, list_idx):
    def ret(p):
        l = p[list_idx]
        l.append[item_idx]
        return l
    return ret

p('translation_unit : package imports entities', p0(lambda p: p[1:]))

p('package :')
p('package : PACKAGE qualified_name', p0(2))

p('imports : ', p0(list))
p('imports : import imports', p0(append(1, 2)))  # TODO reverse

p('import : IMPORT qualified_name', p0(2))

p('entities : ', p0(list))
p('entities : annotated_type entities', p0(append(1, 2)))

p('annotated_type : annotations type', 2)

p('type : module_type', 1)
p('type : interface', 1)
p('type : annotation_type', 1)


#
# Annotation type.
#

p("annotation_type : ANNOTATION Identifier LBRACE annotation_members RBRACE")
p("annotation_members : annotated_annotation_member annotation_members")
p("annotation_members :")

p("annotated_annotation_member : annotations option")


#
# Interfaces and features.
#

# interface Name (extends ...)? { ... }
p("interface : INTERFACE Identifier super_interfaces LBRACE features RBRACE")

# (extends ...)?
p("super_interfaces : EXTENDS reference_list")
p("super_interfaces :")

# AnnotatedInterfaceMember*
p("features : annotated_feature features")
p("features :")

p("annotated_feature : annotations feature")

# feature Name (extends ...)?
p("feature : FEATURE Identifier super_features")

# (extends ...)?
p("super_features : EXTENDS reference_list")
p("super_features :")

#
# Modules.
#

# (abstract)? module Name (extends ...)? { ... }
p("module_type : module_modifiers MODULE Identifier super_module "
        "LBRACE module_members RBRACE")

# ModuleModifier*
p("module_modifiers : module_modifier module_modifiers")
p("module_modifiers : ")

p("module_modifier : STATIC")
p("module_modifier : ABSTRACT")

# (extends ...)?
p("super_module : EXTENDS reference")
p("super_module :")

# AnnotatedModuleMember*
p("module_members : annotated_module_member module_members")
p("module_members :")

p("annotated_module_member : annotations module_member")
p("module_member : DEPENDS  reference_list")
p("module_member : PROVIDES reference_list")
p("module_member : REQUIRES reference_list")
p("module_member : SOURCE   filename_list")
p("module_member : OBJECT   filename_list")
p("module_member : OPTION   option")

# Item ( , Item )*
p("reference_list : reference COMMA reference_list")
p("reference_list : reference")

# ( string | number | boolean | Type ) Name ( = ...)?
p("option : option_type Identifier option_default_value")
p("option_type : STRING")
p("option_type : NUMBER")
p("option_type : BOOLEAN")
p("option_type : reference")

p("option_default_value : EQUALS value")
p("option_default_value :")

p("filename_list : filename COMMA filename_list")
p("filename_list : filename")

p("filename : StringLiteral")

p("annotations : annotation annotations")
p("annotations :")

p("annotation : AT reference annotation_initializer")
p("annotation_initializer : LPAREN parameters_list RPAREN")
p("annotation_initializer : LPAREN value RPAREN")
p("annotation_initializer : ")

#
# Comma-separated list of param=value pairs.
#

p("parameters_list : parameter COMMA parameters_list")
p("parameters_list : parameter")

p("parameter : simple_reference EQUALS value")

p("value : StringLiteral")
p("value : NumberLiteral")
p("value : BooleanLiteral")
p("value : reference")

#
# Datatypes.
#

p("reference : qualified_name")
p("simple_reference : Identifier")

#
# Extended identifiers.
#

p("qualified_name : Identifier PERIOD qualified_name")
p("qualified_name : Identifier")

p("qualified_name_with_wildcard : qualified_name WILDCARD")
p("qualified_name_with_wildcard : qualified_name")


def p_empty(t):
    'empty : '
    pass

def p_error(t):
    print("Whoa. We're hosed")


parser = ply.yacc.yacc(method='LALR')

if __name__ == "__main__":
    ply.yacc.runmain(parser)



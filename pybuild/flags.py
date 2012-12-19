
import os

CPPFLAGS  = ['-D__EMBOX__']
CPPFLAGS += ['-D__impl_x(path)=<%s/src/path>' % (os.getcwd(),)]
CPPFLAGS += ['-nostdinc']
#CPPFLAGS += ['-MMD', '-MP#', '-MT', '$@', '-MF', '$(@:.o=.d)
#CPPFLAGS += -I$(SRC_DIR)/include -I$(SRC_DIR)/arch/$(ARCH)/include
#CPPFLAGS += -I$(SRCGEN_DIR)/include -I$(SRCGEN_DIR)/src/include
#__srcgen_includes := $(addprefix $(SRCGEN_DIR)/src/,include arch/$(ARCH)/include)
#$(and $(shell $(MKDIR) $(__srcgen_includes)),)
#override CPPFLAGS += $(__srcgen_includes:%=-I%)
## XXX reduntand flags, agrrrr -- Eldar
#override CPPFLAGS += $(if $(value PLATFORM),-I$(PLATFORM_DIR)/$(PLATFORM)/include)
#override CPPFLAGS += -I$(SRC_DIR)/compat/linux/include -I$(SRC_DIR)/compat/posix/include

# Assembler flags
ASFLAGS   = ['-pipe']

CXXFLAGS  = ['-pipe']
CXXFLAGS += ['-fno-strict-aliasing', '-fno-common']
CXXFLAGS += ['-Wall', '-Werror']
CXXFLAGS += ['-Wundef', '-Wno-trigraphs', '-Wno-char-subscripts']
CXXFLAGS += ['-Wformat', ' -Wformat-nonliteral']
CXXFLAGS += ['-I$(SRC_DIR)/include/c++']
CXXFLAGS += ['-D"__BEGIN_DECLS=extern \"C\" {"']
CXXFLAGS += ['-D"__END_DECLS=}"']
#        C++ has build-in type bool
CXXFLAGS += ['-DSTDBOOL_H_']

# Compiler flags
CFLAGS  = ['-std=gnu99']
CFLAGS += ['-fno-strict-aliasing', '-fno-common']
CFLAGS += ['-Wall', '-Werror']
CFLAGS += ['-Wstrict-prototypes', '-Wdeclaration-after-statement']
CFLAGS += ['-Wundef', '-Wno-trigraphs', '-Wno-char-subscripts']
CFLAGS += ['-Wformat', '-Wformat-nonliteral', '-Wno-format-zero-length']
CFLAGS += ['-pipe']
CFLAGS += ['-D__BEGIN_DECLS=']
CFLAGS += ['-D__END_DECLS=']

# Linker flags
LDFLAGS = ['-static', '-nostdlib']

ARFLAGS = ['rcs']

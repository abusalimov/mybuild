
TARGET = 'embox'

ARCH = 'x86'

CFLAGS = ['-O0', '-g']
CFLAGS += ['-m32', '-march=i386', '-fno-stack-protector', '-Wno-array-bounds']

LDFLAGS = ['-N', '-g', '-m', 'elf_i386' ]

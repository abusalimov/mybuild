
export ROOT_DIR       := .
export BUILD_DIR      := $(ROOT_DIR)/build/
export CONF_DIR       := $(ROOT_DIR)/conf

export RM     := rm -f
export MKDIR  := mkdir -p
export WAF    := $(ROOT_DIR)/waf


PHONY: all clean

all:
	

config:
	$(WAF) configure
		
clean:
	$(RM) $(BUILD_DIR) 

export ROOT_DIR       := .

export WAF    := $(ROOT_DIR)/waf


.PHONY: all build

all: build

config:
	$(WAF) configure

build:
	$(WAF) build

clean:
	$(WAF) clean


def include(name, opts={}):
    global __modconstr
    __modconstr.append((name, BoolDom([True])))
    for opt_name, value in opts.items():
	__modconstr.append(("%s.%s" % (name, opt_name), Domain([value])))

def exclude(name):
    pass


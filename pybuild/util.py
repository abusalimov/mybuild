
def isvector(obj, len = -1):
    ans = isinstance(obj, tuple) or isinstance(obj, list)

    if len > 0:
	ans &= len(obj) == len

    return ans

def one_or_many(obj):
    return obj if tup_or_list(obj) else [obj]


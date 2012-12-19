
def isvector(obj, len = -1):
    ans = isinstance(obj, tuple) or isinstance(obj, list)

    if len > 0:
        ans &= len(obj) == len

    return ans


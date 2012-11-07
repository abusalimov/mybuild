"""
Misc stuff. --Eldar
"""

def singleton(cls):
    """Decorator for declaring and instantiating a class in-place."""
    return cls()

def unique(iterable, key=id):
    """
    List unique elements, preserving order. Remember all elements ever seen.
    """
    seen = set()
    seen_add = seen.add
    for element in iterable:
        k = key(element)
        if k not in seen:
            seen_add(k)
            yield element


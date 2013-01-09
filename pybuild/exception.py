
class OptException(Exception):
    def __init__(self, opt):
        self.opt = opt 

    def __str__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.opt)

class NotDefinedException(OptException):
    pass

class MultiValueException(OptException):
    pass

class CutConflictException(Exception):
    pass


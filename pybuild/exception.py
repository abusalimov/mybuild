
class MultiValueException(Exception):
    def __init__(self, opt):
        self.opt = opt 

class CutConflictException(Exception):
    def __init__(self, opt, scope):
        self.opt = opt 
        self.scope = scope

    def __str__(self):
        return self.opt


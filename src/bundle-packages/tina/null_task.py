from . import *


@A.register
class Def(IRun):
    '''
    Name: null_task
    Category: task
    Inputs:
    Output: task:t
    '''

    def __init__(self):
        pass

    def run(self):
        pass



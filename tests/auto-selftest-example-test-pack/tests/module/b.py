import stbt

from . import a

class TruthyFrameObjectB(stbt.FrameObject):
    @property
    def is_visible(self):
        return True

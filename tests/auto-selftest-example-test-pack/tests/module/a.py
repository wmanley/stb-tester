import stbt

class TruthyFrameObjectA(stbt.FrameObject):
    @property
    def is_visible(self):
        return True

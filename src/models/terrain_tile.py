from abc import ABC


class GameUnit(ABC):
    def __init__(self, args):
        self.args = args
        self.health = 0
        self.attack = 0
        self.defense = 0

    def returns(self):
        pass

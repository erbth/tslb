"""
A simple, list based stack implementation.
"""


class stack(object):
    def __init__(self):
        super().__init__()
        self.l = []


    def push(self, e):
        self.l.append(e)

    def pop(self):
        e = self.l[-1]
        del self.l[-1]
        return e

    @property
    def top(self):
        return self.l[-1]

    @property
    def empty(self):
        return not bool(self.l)

    def __len__(self):
        return len(self.l)

    def __in__(self, e):
        return e in self.l

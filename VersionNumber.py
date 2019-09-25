"""
Version numbers that are composed of multiple positive int components.
Mixed component types are also supported.

And, 2.0 != 2.0.0. This is because Postgresql's integer array comparision is
like that and I want to use it for comparing version numbers, and moreover
it because it makes a difference if you say `Version 2' or `Version 2.0' (the
last one tends to sound more like a big `thing').
And 1.0 < 1.0.0 because a) Postgresql does that and b) it's nice to have a
strict order (You'd said that, too, wouldn't you? ;-)).
"""

from sqlalchemy import types

class VersionNumber(object):
    """
    Version numbers that are composed of multiple positive int components.
    Mixed component types are also supported.
    """

    def __init__(self, *argument):
        self.components = []

        if len(argument) == 1:
            argument = argument[0]

        if isinstance(argument, str):
            for c in argument.split('.'):
                c = c.strip()
                if c == '':
                    raise ValueError('The individual components may not be empty.')
                try:
                    c = int(c)
                    if c < 0:
                        raise Exception

                except:
                    raise ValueError('The individual components must be positive integers (including 0).')

                self.components.append(c)

        elif isinstance(argument, int):
            if argument < 0:
                raise ValueError('int components must be positive.')
            self.components.append(argument)

        elif isinstance(argument, list) or isinstance(argument, tuple):
            for c in argument:
                if isinstance(c, str):
                    c = c.strip()
                    if c.find('.') >= 0:
                        raise ValueError('The individual components may not contain dots.')

                    try:
                        c = int(c)
                        if c < 0:
                            raise Exception

                    except:
                        raise ValueError('The individual components must be positive integers (including 0).')

                    self.components.append(c)

                elif isinstance(c, int):
                    if c < 0:
                        raise ValueError('int components must be positive.')
                    self.components.append(c)
                else:
                    raise TypeError('Only str and int are supported for component types.')

        elif isinstance(argument, VersionNumber):
            self.components = list(argument.components)

        else:
            raise TypeError('The argument must be str, int, tuple or list of int and strs (may be mixed), or another VersionNumber.')

        if len(self.components) == 0:
            raise ValueError('At least one component must be provided.')

    def __str__(self):
        s = ''
        for c in self.components:
            if len(s) > 0:
                s += '.'
            s += str(c)

        return s

    def __repr__(self):
        return "VersionNumber(%s)" % self.components


    def __lt__(self, other):
        l1 = len(self.components)
        l2 = len(other.components)

        for i in range(min(l1,l2)):
            cs = self.components[i]
            co = other.components[i]
            if cs.__class__ != co.__class__:
                raise NotImplemented

            if cs < co:
                return True
            elif cs > co:
                return False

        if l2 > l1:
            return True

        return False

    def __le__(self, other):
        l1 = len(self.components)
        l2 = len(other.components)

        for i in range(min(l1,l2)):
            cs = self.components[i]
            co = other.components[i]
            if cs.__class__ != co.__class__:
                raise NotImplemented

            if cs < co:
                return True
            elif cs > co:
                return False

        if l1 > l2:
            return False

        return True

    def __eq__(self, other):
        l1 = len(self.components)
        l2 = len(other.components)

        for i in range(min(l1,l2)):
            if self.components[i] != other.components[i]:
                return False

        if l1 != l2:
            return False

        return True

    def __ne__(self, other):
        return self.components != other.components

    def __gt__(self, other):
        return other < self

    def __ge__(self, other):
        return other <= self

    def __hash__(self):
        return hash(tuple(self.components))

class VersionNumberColumn(types.TypeDecorator):
    """
    Represents VersionNumbers in object relational databases
    """
    impl = types.ARRAY(types.Integer)

    def process_bind_param(self, value, dialect):
        return value.components

    def process_result_value(self, value, dialect):
        return VersionNumber(value)

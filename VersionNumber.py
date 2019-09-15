"""
Version numbers that are composed of multiple str or positive int components.
Mixed component types are also supported.
"""

from sqlalchemy import types

class VersionNumber(object):
    """
    Version numbers that are composed of multiple str or positive int components.
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
            if c != self.components[0]:
                s += '.'
            s += str(c)

        return s

    def __repr__(self):
        return "VersionNumber(%s)" % self.components


    def __lt__(self, other):
        for i in range(min(len(self.components), len(other.components))):
            cs = self.components[i]
            co = other.components[i]
            if cs.__class__ != co.__class__:
                raise NotImplemented

            if cs < co:
                return True
            elif cs > co:
                return False

        if len(other.components) > len(self.components):
            co = other.componentsp[i+1]
            if isinstance(co, int) and co > 0:
                return True
            else:
                # A string component is more than nothing.
                return True

        return False

    def __le__(self, other):
        for i in range(min(len(self.components), len(other.components))):
            cs = self.components[i]
            co = other.components[i]
            if cs.__class__ != co.__class__:
                raise NotImplemented

            if cs < co:
                return True
            elif cs > co:
                return False

        return True

    def __eq__(self, other):
        return self.components == other.components

    def __ne__(self, other):
        return self.components != other.components

    def __gt__(self, other):
        return other < self

    def __ge__(self, other):
        return other <= self

    def __hash__(self):
        return hash(self.components)

class VersionNumberColumn(types.TypeDecorator):
    """
    Represents VersionNumbers in object relational databases
    """
    impl = types.ARRAY(types.String)

    def process_bind_param(self, value, dialect):
        def anotate(c):
            if isinstance(c, int):
                return 'i%s' % c
            else:
                return 's' + c

        return [ annotate(c) for c in value.components ]

    def process_result_value(self, value, dialect):
        def unanotate(c):
            if c[0] == 'i':
                return int(c[1:])
            else:
                return c[1:]

        return VersionNumber([ unannotate(c) for c in value ])

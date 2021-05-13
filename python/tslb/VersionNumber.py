"""
Version numbers that are composed of multiple positive int components.
Mixed component types are also supported.

And, 2.0 != 2.0.0. This is because Postgresql's integer array comparision is
like that and I want to use it for comparing version numbers, and moreover
it because it makes a difference if you say `Version 2' or `Version 2.0' (the
last one tends to sound more like a big `thing').
And 1.0 < 1.0.0 because a) Postgresql does that and b) it's nice to have a
strict order (You'd said that, too, wouldn't you? ;-)).

Appended letters like in 1.1.0h are mapped to an extra component (for OpenSSL).
All appended letters represent one component, so 'ad' means a * |{a..z}| + d =
1 * 26 + 4 = 30; like in ieee802.3ad. To distinguish them from ordinary int
components, 1,000,000,000 is added to them. Case does not matter.

Therefore, each int component must not be greater than 999,999,999
"""

from sqlalchemy import types
from tslb.parse_utils import split_on_number_edge
import re

class VersionNumber(object):
    """
    Version numbers that are composed of multiple positive int components.
    Mixed component types are also supported.
    """

    def __init__(self, *argument):
        self.components = []

        if (isinstance(argument, list) or isinstance(argument, tuple)) and len(argument) == 1:
            argument = argument[0]

        if isinstance(argument, str):
            self._init_list(argument.split('.'))

        elif isinstance(argument, int):
            self._init_list([argument])

        elif isinstance(argument, list) or isinstance(argument, tuple):
            self._init_list(argument)

        elif isinstance(argument, VersionNumber):
            self.components = list(argument.components)

        else:
            raise TypeError('The argument must be str, int, tuple or list of int and strs (may be mixed), or another VersionNumber.')

        if len(self.components) == 0:
            raise ValueError('At least one component must be provided.')

    def _init_list(self, argument):
        for ac in argument:
            if isinstance(ac, str):
                ac = ac.strip().casefold()
                if ac.find('.') >= 0:
                    raise ValueError('The individual components may not contain dots.')

                l = split_on_number_edge(ac)

                for c in l:
                    c = c.strip()

                    if re.match('^[a-z]*$', c):
                        # Character component
                        c2 = ''
                        for letter in c:
                            c2 = letter + c2

                        significance = 1
                        n = 0
                        for letter in c2:
                            n += (ord(letter) - 96) * significance
                            significance *= 26

                        c = n + 1_000_000_000

                    else:
                        # Int component
                        try:
                            c = int(c)
                            if c < 0 or c > 999_999_999:
                                raise Exception

                        except:
                            raise ValueError('The individual components must be positive integers in the range [0, 999,999,999], or character strings with a-z.')

                    self.components.append(c)

            elif isinstance(ac, int):
                if ac < 0 or ac > 999_999_999:
                    raise ValueError('int components must be in the range [0, 999,999,999].')
                self.components.append(ac)
            else:
                raise TypeError('Only str and int are supported for component types.')

    def __str__(self):
        s = ''
        for c in self.components:
            if len(s) > 0:
                s += '.'

            if c > 999_999_999:
                c -= 1_000_000_000
                tmp = ''

                while c > 0:
                    tmp += chr(c % 26 + 96)
                    c = c // 26

                comp = ''
                for e in tmp:
                    comp = e + comp

                s += comp
            else:
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
                raise NotImplementedError

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
                raise NotImplementedError

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
        if value is None:
            return None

        return value.components

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        v = VersionNumber(0)
        v.components = value
        return v

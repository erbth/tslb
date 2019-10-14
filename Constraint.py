"""
Constraints for i.e. version numbers.
"""
from VersionNumber import VersionNumber
from CommonExceptions import SavedYourLife

CONSTRAINT_TYPE_NONE    = 0
CONSTRAINT_TYPE_EQ      = 1
CONSTRAINT_TYPE_NEQ     = 2
CONSTRAINT_TYPE_GT      = 3
CONSTRAINT_TYPE_GTE     = 4
CONSTRAINT_TYPE_LT      = 5
CONSTRAINT_TYPE_LTE     = 6

constraint_type_string = {
        CONSTRAINT_TYPE_NONE: '',
        CONSTRAINT_TYPE_EQ: '=',
        CONSTRAINT_TYPE_NEQ: '!=',
        CONSTRAINT_TYPE_GT: '>',
        CONSTRAINT_TYPE_GTE: '>=',
        CONSTRAINT_TYPE_LT: '<',
        CONSTRAINT_TYPE_LTE: '<='
        }

constraint_string_type = {
        '': CONSTRAINT_TYPE_NONE,
        '=': CONSTRAINT_TYPE_EQ,
        '!=': CONSTRAINT_TYPE_NEQ,
        '>': CONSTRAINT_TYPE_GT,
        '>=': CONSTRAINT_TYPE_GTE,
        '<': CONSTRAINT_TYPE_LT,
        '<=': CONSTRAINT_TYPE_LTE
        }

class VersionConstraint(object):
    """
    Constrains a version number. It is like x ⋅ version_number; be ⋅ a
    constraint relation (type).
    """
    def __init__(self, constraint_type, version_number):
        """
        :param constraint_type: The type of constraint.
        :type constraint_type: int or str
        """
        version_number = VersionNumber(version_number)

        try:
            if isinstance(constraint_type, str):
                constraint_type = constraint_string_type[constraint_type]
            elif isinstance(constraint_type, int):
                if constraint_type not in constraint_type_string.keys():
                    raise Exception
            else:
                raise Exception

        except:
            raise InvalidConstraintType(constraint_type)

        self.constraint_type = constraint_type
        self.version_number = version_number

    def fulfilled(self, vn):
        """
        Check if a given version number fulfilles this constraint.

        :param vn: The version number
        :type vn: VersionNumber
        """
        if self.constraint_type == CONSTRAINT_TYPE_NONE:
            return True
        elif self.constraint_type == CONSTRAINT_TYPE_EQ:
            return vn == self.version_number
        elif self.constraint_type == CONSTRAINT_TYPE_NEQ:
            return vn != self.version_number
        elif self.constraint_type == CONSTRAINT_TYPE_GT:
            return vn > self.version_number
        elif self.constraint_type == CONSTRAINT_TYPE_GTE:
            return vn >= self.version_number
        elif self.constraint_type == CONSTRAINT_TYPE_LT:
            return vn < self.version_number
        elif self.constraint_type == CONSTRAINT_TYPE_LTE:
            return vn <= self.version_number
        else:
            raise SavedYourLife

    def is_compatible(self, ovc):
        """
        Test if this version constraint is compatible to another version
        constraint.

        a and b are compatible if there is at least one version number that
        satisfies both, i.e. a set that is constrained by both is not empty.

        :param ovc: The other version constraint
        :type ovc: VersionConstraint
        """
        if self.constraint_type == CONSTRAINT_TYPE_NONE:
            return True

        elif self.constraint_type == CONSTRAINT_TYPE_EQ:
            if ovc.constraint_type == CONSTRAINT_TYPE_NONE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_EQ:
                return ovc.version_number == self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_NEQ:
                return ovc.version_number != self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_GT:
                return ovc.version_number < self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_GTE:
                return ovc.version_number <= self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_LT:
                return ovc.version_number > self.version_number
            else:
                return ovc.version_number >= self.version_number

        elif self.constraint_type == CONSTRAINT_TYPE_NEQ:
            return ovc.constraint_type != CONSTRAINT_TYPE_EQ or ovc.version_number != self.version_number

        elif self.constraint_type == CONSTRAINT_TYPE_GT:
            if ovc.constraint_type == CONSTRAINT_TYPE_NONE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_EQ:
                return ovc.version_number > self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_NEQ:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GT:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GTE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_LT:
                return ovc.version_number > self.version_number
            else:
                return ovc.version_number > self.version_number

        elif self.constraint_type == CONSTRAINT_TYPE_GTE:
            if ovc.constraint_type == CONSTRAINT_TYPE_NONE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_EQ:
                return ovc.version_number >= self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_NEQ:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GT:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GTE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_LT:
                return ovc.version_number > self.version_number
            else:
                return ovc.version_number >= self.version_number

        elif self.constraint_type == CONSTRAINT_TYPE_LT:
            if ovc.constraint_type == CONSTRAINT_TYPE_NONE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_EQ:
                return ovc.version_number < self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_NEQ:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GT:
                return ovc.version_number < self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_GTE:
                return ovc.version_number < self.version_number
            else:
                return True

        else:
            # self.constraint_type == CONSTRAINT_TYPE_LTE
            if ovc.constraint_type == CONSTRAINT_TYPE_NONE:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_EQ:
                return ovc.version_number < self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_NEQ:
                return True
            elif ovc.constraint_type == CONSTRAINT_TYPE_GT:
                return ovc.version_number < self.version_number
            elif ovc.constraint_type == CONSTRAINT_TYPE_GTE:
                return ovc.version_number <= self.version_number
            else:
                return True

    def __eq__(self, other):
        return self.constraint_type == other.constraint_type and\
                self.version_number == other.version_number

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "%s %s" % (constraint_type_string[self.constraint_type], self.version_number)


class DependencyList(object):
    """
    A list of dependencies that consist of an object (say a string) and a
    VersionConstraint. The list makes sure that it contains fewest elements
    possible for each object and selects the strongest constraints to be kept
    when a new (object, constraint) pair is added.

    It is more like an imaginary, possibly infinite set that contains all
    possible object/version combinations. To test if an object/version pair is
    in this set, use `(o, version_number) in dl', where dl is a DependencyList.

    Initially

    Maybe it's a list of sets?
    Well, there're requirements and constraints. Basically constraints on
    required versions.
    """
    def __init__(self):
        self.l = {}

    def add_constraint(self, vc, o):
        """
        :param vc: A version constraint
        :type vc: VersionConstraint
        :param o: Any object that is hashable.
        :except: May rise a ConstraintContradiction
        """
        if o in self.l and len(self.l[o]) > 0:
            # In the list might be: a < or <=, a > or >=, multiple !=, or only
            # one = as well as only one ''.

            # First, check compatibility
            if not all([ vc.is_compatible(ovc) for ovc in self.l[o] ]):
                raise ConstraintContradiction

            # Second, test if the version number is contained in the object's
            # set (it can further constrain the set only then).
            if self.__contains__((o, vc.version_number)):
                # Third, decide by the type of the new constraint and the shape
                # of the list what shall be done.
                #
                # There can be at least one gt(e) and one lt(e).
                gt = None
                gt_index = 0
                lt = None
                lt_index = 0
                eq = None

                for i, e in enumerate(self.l[o]):
                    if e.constraint_type == CONSTRAINT_TYPE_GT or e.constraint_type == CONSTRAINT_TYPE_GTE:
                        gt = e
                        gt_index = i

                    elif e.constraint_type == CONSTRAINT_TYPE_LT or e.constraint_type == CONSTRAINT_TYPE_LTE:
                        lt = e
                        lt_index = i

                    elif e.constraint_type == CONSTRAINT_TYPE_EQ:
                        eq = e

                # Five shapes:
                # {x}
                if eq is not None:
                    # We know the new constraint is compatible. We cannot restrict
                    # the list further.
                    pass

                # Each of the following shapes may have holes.
                # (-inf, +inf)
                elif gt is None and lt is None:
                    if vc.constraint_type == CONSTRAINT_TYPE_NONE:
                        pass
                    elif vc.constraint_type == CONSTRAINT_TYPE_EQ:
                        # It is compatible hence not in a hole ...
                        self.l[o] = [vc]
                    else:
                        self.l[o].append(vc)
                        self.l[o] = list(filter(lambda ovc:\
                                ovc.constraint_type != CONSTRAINT_TYPE_NONE and\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                # (-inf, x)]
                elif gt is None:
                    if vc.constraint_type == CONSTRAINT_TYPE_NONE:
                        pass
                    elif vc.constraint_type == CONSTRAINT_TYPE_EQ:
                        # It is compatible hence not in a hole and inside the range.
                        self.l[o] = [vc]
                    elif vc.constraint_type == CONSTRAINT_TYPE_NEQ:
                        # Is it at the border? (It can only be at a closed border ...)
                        if lt.constraint_type == CONSTRAINT_TYPE_LTE and\
                                vc.version_number == lt.version_number:
                            self.l[o][lt_index].constraint_type = CONSTRAINT_TYPE_LT
                        else:
                            # The list has a not-None element already, hence no
                            # filtering is required.
                            self.l[o].append(vc)

                    elif vc.constraint_type == CONSTRAINT_TYPE_LT or\
                            vc.constraint_type == CONSTRAINT_TYPE_LTE:
                        self.l[o][lt_index] = vc

                        # Remove now useless neqs
                        self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                    elif vc.constraint_type == CONSTRAINT_TYPE_GT or\
                            vc.constraint_type == CONSTRAINT_TYPE_GTE:
                        # The interval can only be one element wide if both borders
                        # are closed and equal. If they are equal, the interval
                        # must be closed (because it would be of size 0 otherwise,
                        # which would be a contradiction).
                        if vc.version_number == lt.version_number:
                            self.l[o] = [VersionConstraint(CONSTRAINT_TYPE_EQ, vc.version_number)]
                        else:
                            self.l[o].append(vc)
                            # Remove now useless neqs
                            self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                # [(x, +inf)
                elif lt is None:
                    if vc.constraint_type == CONSTRAINT_TYPE_NONE:
                        pass
                    elif vc.constraint_type == CONSTRAINT_TYPE_EQ:
                        # It is compatible hence not in a hole and inside the range.
                        self.l[o] = [vc]
                    elif vc.constraint_type == CONSTRAINT_TYPE_NEQ:
                        # Is it at the border? (It can only be at a closed border ...)
                        if gt.constraint_type == CONSTRAINT_TYPE_GTE and\
                                vc.version_number == gt.version_number:
                            self.l[o][gt_index].constraint_type = CONSTRAINT_TYPE_GT
                        else:
                            # The list has a not-None element already, hence no
                            # filtering is required.
                            self.l[o].append(vc)

                    elif vc.constraint_type == CONSTRAINT_TYPE_GT or\
                            vc.constraint_type == CONSTRAINT_TYPE_GTE:
                        self.l[o][gt_index] = vc

                        # Remove now useless neqs
                        self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                    elif vc.constraint_type == CONSTRAINT_TYPE_LT or\
                            vc.constraint_type == CONSTRAINT_TYPE_LTE:
                        # The interval can only be one element wide if both borders
                        # are closed and equal. If they are equal, the interval
                        # must be closed (because it would be of size 0 otherwise,
                        # which would be a contradiction).
                        if vc.version_number == gt.version_number:
                            self.l[o] = [VersionConstraint(CONSTRAINT_TYPE_EQ, vc.version_number)]
                        else:
                            self.l[o].append(vc)
                            # Remove now useless neqs
                            self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                # [(x, y)]
                else:
                    if vc.constraint_type == CONSTRAINT_TYPE_NONE:
                        pass
                    if vc.constraint_type == CONSTRAINT_TYPE_EQ:
                        # It's compatible hence in the interval.
                        self.l[o] = [vc]
                    elif vc.constraint_type == CONSTRAINT_TYPE_NEQ:
                        # At a closed border?
                        if vc.version_number == lt.version_number:
                            self.l[o][lt_index].constraint_type = CONSTRAINT_TYPE_LT
                        elif vc.version_number == gt.version_number:
                            self.l[o][gt_index].constraint_type = CONSTRAINT_TYPE_GT
                        else:
                            # No? - simply add it.
                            self.l[o].append(vc)

                    elif vc.constraint_type == CONSTRAINT_TYPE_LT or\
                            vc.constraint_type == CONSTRAINT_TYPE_LTE:
                        # The interval can only be one element wide if both borders
                        # are closed and equal. If they are equal, the interval
                        # must be closed (because it would be of size 0 otherwise,
                        # which would be a contradiction).
                        if vc.version_number == gt.version_number:
                            self.l[o] = [VersionConstraint(CONSTRAINT_TYPE_EQ, vc.version_number)]
                        else:
                            self.l[o][lt_index] = vc

                            # Remove now useless neqs
                            self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

                    elif vc.constraint_type == CONSTRAINT_TYPE_GT or\
                            vc.constraint_type == CONSTRAINT_TYPE_GTE:
                        # The interval can only be one element wide if both borders
                        # are closed and equal. If they are equal, the interval
                        # must be closed (because it would be of size 0 otherwise,
                        # which would be a contradiction).
                        if vc.version_number == lt.version_number:
                            self.l[o] = [VersionConstraint(CONSTRAINT_TYPE_EQ, vc.version_number)]
                        else:
                            self.l[o][gt_index] = vc

                            # Remove now useless neqs
                            self.l[o] = list(filter(lambda ovc:\
                                (vc.constraint_type != CONSTRAINT_TYPE_NEQ or vc.fulfilled(ovc.version_number)), self.l[o]))

        else:
            self.l[o] = [vc]

    def get_required(self):
        """
        Objects that are required, hence those I want.
        """
        return list(self.l.keys())

    def __contains__(self, t):
        """
        Object versions that are compatible with me. Specify what I want more
        precisely.

        If one views the dependencies of a single object asa set of allowed
        version number, this tests if the given version number is contained.

        :param t: tuple(o, version_number)
        """
        o, vn = t
        vn = VersionNumber(vn)

        if o in self.l:
            # Check if vn is compatible with my requirements.
            return all([ vc.fulfilled(vn) for vc in self.l[o] ])
        else:
            return True

    def get_constraint_list(self, o):
        return self.l.get(o, [])


# Exceptions for useful error messages
class InvalidConstraintType(Exception):
    def __init__(self, ctype):
        super().__init__("Invalid constraint type `%s'" % ctype)

class ConstraintContradiction(Exception):
    def __init__(self):
        super().__init__("Constraint contradiction.")

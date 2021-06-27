import os
import re
import subprocess
import tempfile
from tslb import Constraint
from tslb.Constraint import DependencyList
from tslb.VersionNumber import VersionNumber
from . import config_file_utils as cfu


def ask_set_None(rw):
    if not rw:
        return False

    while True:
        resp = input("Edit value or set to None? [E/n]")

        if resp == 'e' or resp == 'E' or resp == '':
            return False
        elif resp == 'n' or resp == 'N':
            return True


def edit_object_None(rw):
    if not rw:
        print("The current value is `None'.")
        return None

    while True:
        print("The current value is `None'.\nChoose a new type from the list below or input nothing to abort.")
        print("  (1) str")
        print("  (2) List(str)")
        print("  (3) List(Tuple(str, str|List(str)))")
        print("  (4) DependencyList with str objects")
        print("  (5) List(Tuple(str, DependencyList(str)))")

        _type = input("> ")

        if _type == '':
            return None

        elif _type == '1':
            return edit_object_str('', rw)

        elif _type == '2':
            return edit_object_list_str([], rw)

        elif _type == '3':
            return edit_object_list_pair_of_str_str_list([], rw)

        elif _type == '4':
            return edit_object_dependency_list_str(DependencyList(), rw)

        elif _type == '5':
            return edit_object_list_pair_of_str_dependency_list_str(list(), rw)


def edit_object_str(string, rw):
    # Create a temporary file
    fd, path = tempfile.mkstemp()

    try:
        os.write(fd, string.encode('UTF-8'))
        os.close(fd)

        if not rw:
            os.chmod(path, 0o400)

        # Run an editor on it
        ret = subprocess.run(['editor', path])

        if ret.returncode == 0 and rw:
            # Fetch the new content
            with open(path, 'rb') as f:
                new_value = f.read().decode('UTF-8')

                if new_value.count('\n') == 1 and new_value.endswith('\n'):
                    print("one-line value, stripping trailing newline.")
                    new_value = new_value[:-1]

                return new_value

        return string


    finally:
        # Delete the temporary file again
        os.unlink(path)


def edit_object_list_str(obj, rw):
    # Convert the list to a config-file like string
    string = "# You are editing a list of str.\n" \
             "# Be aware that order matters. Empty lines are removed.\n"

    for e in obj:
        string += e + "\n"

    # Edit and parse back
    # Let the user view / edit the string
    string = edit_object_str(string, rw)

    if not rw:
        return obj

    # Remove comments and interpret as newline-separated list
    list_ = []
    for line in string.split('\n'):
        line = re.sub(r'#.*', '', line).strip()
        if not line:
            continue

        list_.append(line)

    return list_


def edit_object_list_pair_of_str_str_list(obj, rw):
    # Convert the list to a config-file like string
    string = "# You are editing a list of pairs (str, str | list(str)).\n" \
             "# Be aware that order matters.\n" \
             "# \n" \
             "# This is a comment. A backslash ('\\') in it has not special meaning.\n" \
             "# \n" \
             "# These are a few examples of the syntax used in this file:\n" \
             "# \n" \
             "# \"package\": None                   # A list element (\"package\", None)\n" \
             "# \n" \
             "# \"package2\":                       # Invalid syntax\n" \
             "# \n" \
             "# \"key 2\": \"meow\"                   # A simple key-value pair\n" \
             "# \n" \
             "# \"key 3\": [\"Test\", \"Test2\"]        # List as second value of pair\n" \
             "# \n" \
             "#     \"Meow\"   :  \"Test\"            # Arbitrary spaces are allowed\n" \
             "# \n" \
             "# \"Test\": \\\n" \
             "#    \"Woof\"                         # '\\' continues lines\n" \
             "# \n" \
             "# \"Test3\": \\    # A comment behind a backslash has no special meaning\n" \
             "#    \"Value\"    # <- Accepted normally\n"

    for key, value in obj:
        if isinstance(value, list):
            value = '[' + ', '.join('"%s"' % cfu.escape_string(e) for e in value) + ']'
        else:
            value = '"' + cfu.escape_string(value) + '"'

        string += '"%s": %s\n' % (cfu.escape_string(key), value)


    # Edit and parse back
    while True:
        # Let the user view / edit the string
        string = edit_object_str(string, rw)

        if not rw:
            return obj

        # Parse the string back to a list
        try:
            tmp = cfu.preprocess(string)
            tmp = cfu.tokenize_list_pair_of_str_str_list(tmp)
            tmp = cfu.parse_list_pair_of_str_str_list(tmp)
            return tmp

        except cfu.CFUSyntaxError as e:
            print(str(e))
            print("Press return to continue")
            input()


def edit_object_dependency_list_str(obj, rw):
    # Convert the list to a config-file like string
    string = "# You are editing a DependencyList with str objects.\n" \
             "# \n" \
             "# This is a comment. A backslash ('\\') in it has not special meaning.\n" \
             "# \n" \
             "# These are a few examples of the syntax used in this file:\n" \
             "# \n" \
             "# \"Package 1\" >= 1.3                # Require `Package 1' in version 1.3 or higher\n" \
             "# \"Package 1\" < 4.9 != 3.7          # Additional requirements\n" \
             "# \n" \
             "# package2==3.3                     # Spaces are not important, quotes are optional \n" \
             "#                                   # if Literals have no spaces.\n" \
             "# \n" \
             "#     \"Package 3\"   !=  4           # Arbitrary spaces are allowed\n" \
             "# \n" \
             "# \"Package 4\" \\\n" \
             "#    \"= 5.5\"                        # '\\' continues lines\n" \
             "# \n" \
             "# \"Package 5\": \\     # A comment behind a backslash has no special meaning\n" \
             "#    \"> 1a\"          # <- Accepted normally\n" \
             "# \n" \
             "# Order does not matter, multiple lines with the same key will be collated.\n" \
             "# Allowed version predicates are < > >= <= != == and = (the latter two are identical).\n"

    for package, constraints in sorted(obj.get_object_constraint_list(), key=lambda t: t[0]):
        values = []

        for c in constraints:
            if c.constraint_type != Constraint.CONSTRAINT_TYPE_NONE:
                values.append("%s%s" % (Constraint.constraint_type_string[
                    c.constraint_type], c.version_number))

        string += '"' + cfu.escape_string(package) + '"'

        if values:
            string += ' ' + ' '.join(values)

        string += '\n'


    # Edit and parse back
    while True:
        # Let the user view / edit the string
        string = edit_object_str(string, rw)
        if not rw:
            return obj

        # Parse the string back to a DependencyList
        try:
            tmp = cfu.preprocess(string)
            tmp = cfu.tokenize_dependency_list_str(tmp)
            tmp = cfu.parse_dependency_list_str(tmp)

            new_list = DependencyList()

            for package, constraints in tmp:
                if constraints:
                    for c in constraints:
                        new_list.add_constraint(c, package)

                else:
                    new_list.add_constraint(
                            Constraint.VersionConstraint(
                                Constraint.CONSTRAINT_TYPE_NONE,
                                VersionNumber(0)),
                            package)

            return new_list

        except (cfu.CFUSyntaxError, Constraint.ConstraintContradiction) as e:
            print(str(e))
            print("Press return to continue")
            input()


def edit_object_list_pair_of_str_dependency_list_str(obj, rw):
    # Convert the list to a config-file like string
    string = "# You are editing an object of type list(pair(str, DependencyList(str))).\n" \
             "# \n" \
             "# This is a comment. A backslash ('\\') in it has not special meaning.\n" \
             "# A literal can be enclosed in quotes to allow for spaces in it.\n" \
             "# \n" \
             "# This file's syntax follows these examples:\n" \
             "# bash -> glibc >= 2.24 <= 3.0\n" \
             "# bash -> \"libreadline 1\"\n" \
             "# \n" \
             "# Order does not matter, multiple lines with the same dependency will be collated.\n" \
             "# Allowed version predicates are < > >= <= != == and = (the latter two are identical).\n"

    for bp_name, dl in obj:
        for dep, constraints in sorted(dl.get_object_constraint_list(), key=lambda t: t[0]):
            values = []

            for c in constraints:
                if c.constraint_type != Constraint.CONSTRAINT_TYPE_NONE:
                    values.append("%s%s" % (
                        Constraint.constraint_type_string[c.constraint_type],
                        c.version_number))

            string += '"' + cfu.escape_string(bp_name) + '" -> "' + cfu.escape_string(dep) + '"'
            if values:
                string += ' ' + ' '.join(values)

            string += '\n'


    # Edit and parse back
    while True:
        # Let the user view / edit the string
        string = edit_object_str(string, rw)
        if not rw:
            return obj

        # Parse the string back to a list
        try:
            tmp = cfu.preprocess(string)
            tmp = cfu.tokenize_list_pair_of_str_dependency_list_str(tmp)
            tmp = cfu.parse_list_pair_of_str_dependency_list_str(tmp)

            new_list = []

            for bp_name, dep, constraints in tmp:
                dl = DependencyList()

                if constraints:
                    for c in constraints:
                        dl.add_constraint(c, dep)

                else:
                    dl.add_constraint(
                            Constraint.VersionConstraint(
                                Constraint.CONSTRAINT_TYPE_NONE,
                                VersionNumber(0)),
                            dep)

                new_list.append((bp_name, dl))

            return new_list

        except (cfu.CFUSyntaxError, Constraint.ConstraintContradiction) as e:
            print(str(e))
            print("Press return to continue")
            input()


def edit_object(obj, rw):
    """
    Display an editor for the given object on stdout.

    :param obj: The object to edit
    :param bool rw: True if the object should be editable, False if a read-only
        view shall be presented.
    :returns: The new (possibly changed) object
    :raises UnsupportedObject: if the object is not supported.
    """
    if obj is None:
        return edit_object_None(rw)

    if ask_set_None(rw):
        return None

    if isinstance(obj, str):
        return edit_object_str(obj, rw)

    elif isinstance(obj, list):
        # Look for list(str)
        valid = True

        for e in obj:
            if not isinstance(e, str):
                valid = False
                break

        if valid:
            return edit_object_list_str(obj, rw)

        # Look for list(tuple(str, str|list(str)))
        valid = True

        for e in obj:
            if not isinstance(e, tuple) or len(e) != 2 or not isinstance(e[0], str):
                valid = False
                break

            if isinstance(e[1], list):
                valid2 = True
                for e2 in e[1]:
                    if not isinstance(e2, str):
                        valid2 = False
                        break

                if not valid2:
                    valid = False
                    break

            elif not isinstance(e[1], str):
                valid = False
                break

        if valid:
            return edit_object_list_pair_of_str_str_list(obj, rw)

        # Look for list(tuple(str, DependencyList(str)))
        valid = True

        for e in obj:
            if not isinstance(e, tuple) or len(e) != 2 or \
                    not isinstance(e[0], str) or not isinstance(e[1], DependencyList):
                valid = False
                break

            for o in e[1].get_required():
                if not isinstance(o, str):
                    valid = False
                    break

            if not valid:
                break

        if valid:
            return edit_object_list_pair_of_str_dependency_list_str(obj, rw)

    elif isinstance(obj, DependencyList):
        # Check if objects are strings
        req = obj.get_required()
        if all(isinstance(e, str) for e in req):
            return edit_object_dependency_list_str(obj, rw)

    raise UnsupportedObject(type(obj))


class UnsupportedObject(Exception):
    def __init__(self, _type):
        super().__init__("Unsupported object of type `%s'." % _type)

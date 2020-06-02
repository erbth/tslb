import os
import subprocess
import tempfile
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
        print("  (2) list(tuple(str, str|list(str)))")

        _type = input("> ")

        if _type == '':
            return None

        elif _type == '1':
            return edit_object_str('', rw)

        elif _type == '2':
            return edit_object_list_pair_of_str_str_list([], rw)


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

        # Parse the string back to a list
        try:
            tmp = cfu.preprocess(string)
            tmp = cfu.tokenize(tmp)
            tmp = cfu.parse_list_pair_of_str_str_list(tmp)
            return tmp

        except cfu.CFUSyntaxError as e:
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

    if isinstance(obj, list):
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

    raise UnsupportedObject(type(obj))


class UnsupportedObject(Exception):
    def __init__(self, _type):
        super().__init__("Unsupported object of type `%s'." % _type)

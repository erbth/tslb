"""
This module houses a tokenizer and preprocessor for config-file like languages
to edit python objects. Moreover parses for some object types are here, too.

Additionally escaped characters are defined in this module.
"""
from tslb.VersionNumber import VersionNumber
from tslb.Constraint import VersionConstraint


character_escape_map = {
    '"': '\\"',
    '\\': '\\\\',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t'
}

escape_character_map = {v: k for k,v in character_escape_map.items()}

def escape_string(s):
    return ''.join(character_escape_map.get(c, c) for c in s)

def unescape_string(s):
    return ''.join(escape_character_map.get(c, c) for c in s)


def preprocess(s):
    """
    :param str s: Input string
    :returns List(Tuple(int, int, str)): Character string with line and column
        numbers
    """
    output = []

    c1 = None
    in_literal = False
    comment_detected = False
    line_continuation_detected = False

    line = 1
    col = 1

    for c in s:
        if comment_detected:
            if c == '\n':
                comment_detected = False
                line_continuation_detected = False
                output.append((line, col, c))

        elif line_continuation_detected:
            if c == '\n':
                line_continuation_detected = False
            elif c == '#':
                comment_detected = True
            elif not c.isspace():
                raise CFUSyntaxError(line, col, "No non-space characters "
                    "allowed after line continuation (except comments)")

        else:
            if in_literal:
                if c == '"' and c1 != '\\':
                    in_literal = False

                output.append((line, col, c))

            else:
                if c == '#':
                    comment_detected = True

                elif c == '\\':
                    line_continuation_detected = True

                else:
                    output.append((line, col, c))

                    if c == '"':
                        in_literal = True


        # Prepare for next input character
        c1 = c

        col += 1
        if c == '\n':
            col = 1
            line += 1

    return output


def tokenize_list_pair_of_str_str_list(s):
    """
    :param List(Tuple(int, int, str)): Preprocessed input string
    :returns list(int, int, str, bool): Token string of 4-tuples
        (line, column, token, is_literal).
    """
    ts = []

    c1 = None
    current_literal = None
    start_line = 0
    start_column = 0

    line = 0
    col = 0

    for line, col, c in s:
        if current_literal is not None:
            if c1 == '\\':
                # Escape sequence
                if c not in ('"', '\\', 'n', 'r', 't'):
                    raise CFUSyntaxError(line, col, "Invalid escape sequence `\\%s'" % c)

                current_literal += c1 + c

            elif c == '"':
                ts.append((start_line, start_column, current_literal, True))
                current_literal = None

            else:
                current_literal += c

        else:
            if c == '"':
                start_line = line
                start_column = col
                current_literal = ''

            elif c.isspace() and not c == '\n':
                pass

            elif c in (':', ',', '[', ']', '\n'):
                ts.append((line, col, c, False))

            else:
                raise CFUSyntaxError(line, col,
                        "Invalid character `%s', expected a non-literal token (#\\:,[]\\n)" %
                        c)

        # Prepare for next character
        c1 = c


    # The input text must not end with an open literal
    if current_literal is not None:
        raise CFUSyntaxError(line, col, "The input text must not end with an open literal")

    return ts


def parse_list_pair_of_str_str_list(ts):
    """
    :param list(int, int, str, bool) ts: Token string
    """
    # Power set constructed DFA parser
    state = 1
    line = 0
    col = 0

    _list = []

    key = None
    value = None

    for line, col, token, is_literal in ts:
        if state == 1:
            if is_literal:
                key = token
                state = 2

            elif token == '\n':
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected literal or non-literal `\\n'")


        elif state == 2:
            if is_literal or token != ':':
                raise CFUSyntaxError(line, col, "Expected non-literal `:'")

            state = 3

        elif state == 3:
            if is_literal:
                value = token
                state = 7

            elif token == '[':
                value = []
                state = 4

            else:
                raise CFUSyntaxError(line, col, "Expected literal or non-literal `['")

        elif state == 4:
            if is_literal:
                value.append(token)
                state = 5

            elif token == ']':
                state = 7

            else:
                raise CFUSyntaxError(line, col, "Expected literal or non-literal `]'")

        elif state == 5:
            if is_literal or (token != ']' and token != ','):
                raise CFUSyntaxError(line, col, "Expected non-literals `]' or `,'")

            elif token == ']':
                state = 7

            else:
                state = 6

        elif state == 6:
            if is_literal:
                value.append(token)
                state = 5

            else:
                raise CFUSyntaxError(line, col, "Expected literal")

        elif state == 7:
            if not is_literal and token == '\n':
                _list.append((key, value))
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected non-literal `\\n'")

    if state != 1:
        raise CFUSyntaxError(line, col, "Unexpected end of file")

    return _list


def tokenize_dependency_list_str(s):
    """
    :param List(Tuple(int, int, str)): Preprocessed input string
    :returns list(int, int, str, bool): Token string of 4-tuples
        (line, column, token, is_literal).
    """
    ts = []

    c1 = None
    c2 = None
    current_literal = None
    current_quoted = False
    start_line = 0
    start_column = 0

    line = 0
    col = 0
    line1 = 0
    col1 = 0

    for line, col, c in s:
        if current_literal is not None:
            if c1 == '\\':
                # Escape sequence
                if c not in ('"', '\\', 'n', 'r', 't'):
                    raise CFUSyntaxError(line, col, "Invalid escape sequence `\\%s'" % c)

                current_literal += c1 + c

            elif (current_quoted and c == '"') or (not current_quoted and c.isspace()):
                ts.append((start_line, start_column, current_literal, True))
                current_literal = None

                if c == '\n':
                    ts.append((line, col, c, False))

            elif c == '"':
                raise CFUSyntaxError(line, col, "Unescaped quote in unquoted literal")

            else:
                current_literal += c

        else:
            if c1 in ('<', '>', '=') and c != '=' and c2 not in ('<', '>', '=', '!'):
                ts.append((line1, col1, c1, False))

            if c == '"' or (not c.isspace() and c not in ('<', '>', '=', '!')):
                if c == '"':
                    current_quoted = True
                    current_literal = ''
                else:
                    current_quoted = False
                    current_literal = c

                start_line = line
                start_column = col

            elif c.isspace() and not c == '\n':
                pass

            elif (c1 and (c1 + c) in ('<=', '>=', '!=', '==')):
                ts.append((line, col, c1 + c, False))

            elif c == '\n':
                ts.append((line, col, c, False))

            elif c in ('<', '>', '!', '='):
                pass

            else:
                raise CFUSyntaxError(line, col,
                        "Invalid character `%s', expected a non-literal token (#\\:,[]\\n)" %
                        c)

        # Prepare for next character
        c2 = c1
        c1 = c
        line1 = line
        col1 = col


    # The input text must not end with an open literal
    if current_literal is not None and current_quoted:
        raise CFUSyntaxError(line, col, "The input text must not end with an open quote")

    return ts


def parse_dependency_list_str(ts):
    """
    :param list(int, int, str, bool) ts: Token string
    :returns list(tuple(str, list(VersionConstraint))): The parsed constraint
        list
    """
    # Power set constructed DFA parser
    state = 1
    line = 0
    col = 0

    _list = []

    name = None
    constraints = None
    constraint_type = None

    for line, col, token, is_literal in ts:
        if state == 1:
            if is_literal:
                name = token
                constraints = []
                state = 2

            elif token == '\n':
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected literal or non-literal `\\n'")

        elif state == 2:
            if not is_literal and token in ('<', '>', '<=', '>=', '!=', '==', '='):
                constraint_type = token
                state = 3

            elif not is_literal and token == '\n':
                _list.append((name, constraints))
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected non-literal from (< > <= >= != == = \\n)")

        elif state == 3:
            if is_literal:
                try:
                    v = VersionNumber(token)
                except Exception as e:
                    raise CFUSyntaxError(line, col, "Invalid version number `%s': %s" %
                            token, e)

                if constraint_type == '=':
                    constraint_type = '=='

                constraints.append(VersionConstraint(constraint_type, v))
                state = 2

            else:
                raise CFUSyntaxError(line, col, "Expected literal")


    if state != 1:
        raise CFUSyntaxError(line, col, "Unexpected end of file")

    return _list


class CFUSyntaxError(Exception):
    def __init__(self, line, col, text):
        self.line = line
        self.col = col
        self.text = text

        super().__init__("Syntax error on line %d, col %d: %s" % (line, col, text))

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


def preprocess(s):
    """
    :param str s: Input string
    :returns List(Tuple(int, int, str)): Character string with line and column
        numbers
    """
    output = []

    escape = False
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
                if c == '"' and not escape:
                    in_literal = False

                if escape:
                    escape = False
                else:
                    if c == '\\':
                        escape = True

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
                        escape = False


        # Advance column and line counters
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

    escape = False
    current_literal = None
    start_line = 0
    start_column = 0

    line = 0
    col = 0

    for line, col, c in s:
        if current_literal is not None:
            if escape:
                # Escape sequence
                try:
                    current_literal += escape_character_map['\\' + c]
                except KeyError:
                    raise CFUSyntaxError(line, col, "Invalid escape sequence `\\%s'" % c)

                escape = False

            elif c == '"':
                ts.append((start_line, start_column, current_literal, True))
                current_literal = None

            elif c == '\\':
                escape = True

            else:
                current_literal += c

        else:
            if c == '"':
                start_line = line
                start_column = col
                current_literal = ''
                escape = False

            elif c.isspace() and not c == '\n':
                pass

            elif c in (':', ',', '[', ']', '\n'):
                ts.append((line, col, c, False))

            else:
                raise CFUSyntaxError(line, col,
                        "Invalid character `%s', expected a non-literal token (#\\:,[]\\n)" %
                        c)


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
    escape = False
    start_line = 0
    start_column = 0

    line = 0
    col = 0
    line1 = 0
    col1 = 0

    for line, col, c in s:
        if current_literal is not None:
            if escape:
                # Escape sequence
                try:
                    current_literal += escape_character_map['\\' + c]
                except KeyError:
                    raise CFUSyntaxError(line, col, "Invalid escape sequence `\\%s'" % c)

                escape = False

            elif (current_quoted and c == '"') or (not current_quoted and c.isspace()):
                ts.append((start_line, start_column, current_literal, True))
                current_literal = None

                if c == '\n':
                    ts.append((line, col, c, False))

            elif c == '"':
                raise CFUSyntaxError(line, col, "Unescaped quote in unquoted literal")

            elif c == '\\':
                escape = True

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
                escape = False

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
                        "Invalid character `%s', expected a non-literal token" %
                        c)

        # Prepare for next character
        c2 = c1
        c1 = c
        line1 = line
        col1 = col


    # The input text must not end with an open literal
    if current_literal is not None:
        if current_quoted:
            raise CFUSyntaxError(line, col, "The input text must not end with an open quote")

        ts.append((start_line, start_column, current_literal, True))

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
                            (token, e))

                if constraint_type == '==':
                    constraint_type = '='

                constraints.append(VersionConstraint(constraint_type, v))
                state = 2

            else:
                raise CFUSyntaxError(line, col, "Expected literal")


    if state != 1:
        raise CFUSyntaxError(line, col, "Unexpected end of file")

    return _list


def tokenize_list_pair_of_str_dependency_list_str(s):
    """
    :param List(Tuple(int, int, str)): Preprocessed input string
    :returns list(int, int, str, bool): Token string of 4-tuples
        (line, column, token, is_literal).
    """
    # Characters allowed in unquoted string literals
    def is_c(c):
        c = c.encode('utf-8')
        if len(c) != 1:
            return False

        c = c[0]

        if c >= 0x41 and c <= 0x5a:
            return True

        if c >= 0x61 and c <= 0x7a:
            return True

        if c >= 0x30 and c <= 0x39:
            return True

        if c == 0x2e:
            return True

        return False

    # Detect tokens with a DFA parser. Basically tokens are just words on an
    # alphabet and therefore form a language.
    ts = []

    line = 0
    col = 0

    state = 1

    token = ''
    token_line = 0
    token_col = 0

    def add_token(line, col, c):
        nonlocal token, token_line, token_col
        if not token:
            token_line = line
            token_col = col

        token += c


    def finish_token(is_literal):
        nonlocal token
        ts.append((token_line, token_col, token, is_literal))
        token = ''


    for line, col, c in s:
        if state == 1:
            if c == '\n':
                add_token(line, col, c)
                finish_token(False)
                state = 1

            elif c.isspace():
                state = 1

            elif is_c(c):
                add_token(line, col, c)
                state = 2

            elif c == '-':
                add_token(line, col, c)
                state = 3

            elif c == '"':
                state = 4

            elif c in ('>', '<', '='):
                add_token(line, col, c)
                state = 6

            elif c == '!':
                add_token(line, col, c)
                state = 7

            else:
                raise CFUSyntaxError(line, col, "Unexpected character")

        elif state == 2:
            if is_c(c):
                add_token(line, col, c)
                state = 2

            elif c == '\n':
                finish_token(True)
                add_token(line, col, c)
                finish_token(False)
                state = 1

            elif c.isspace():
                finish_token(True)
                state = 1

            elif c in ('>', '<', '='):
                finish_token(True)
                add_token(line, col, c)
                state = 6

            elif c == '!':
                finish_token(True)
                add_token(line, col, c)
                state = 7

            elif c == '"':
                finish_token(True)
                state = 4

            elif c == '-':
                finish_token(True)
                add_token(line, col, c)
                state = 3

            else:
                raise CFUSyntaxError(line, col, "Unexpected character")

        elif state == 3:
            if c == '>':
                add_token(line, col, c)
                finish_token(False)
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected `-'")

        elif state == 4:
            if c == '\\':
                state = 5

            elif c == '"':
                finish_token(True)
                state = 1

            else:
                add_token(line, col, c)
                state = 4

        elif state == 5:
            if c in ('\\', '"', 'n', 'r', 't'):
                add_token(line, col, escape_character_map['\\' + c])
                state = 4

            else:
                raise CFUSyntaxError(line, col,
                        "Invalid escape sequence `\\%s'" % c)

        elif state == 6:
            if c == '\n':
                finish_token(False)
                add_token(line, col, c)
                finish_token(False)
                state = 1

            elif c.isspace():
                finish_token(False)
                state = 1

            elif c in ('>', '<', '='):
                prop_token = token + c
                if prop_token not in ('>', '<', '>=', '<=', '=', '==', '!='):
                    finish_token(False)

                add_token(line, col, c)
                state = 6

            elif c == '!':
                finish_token(False)
                add_token(line, col, c)
                state = 7

            elif is_c(c):
                finish_token(False)
                add_token(line, col, c)
                state = 2

            elif c == '"':
                finish_token(False)
                state = 4

            elif c == '-':
                finish_token(False)
                add_token(line, col, c)
                state = 3

            else:
                raise CFUSyntaxError(line, col, "Unexpected character")

        elif state == 7:
            if c == '=':
                add_token(line, col, '=')
                finish_token(False)
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected `='")


    if state == 3:
        raise CFUSyntaxError(line, col, "Expected `>' at end of input")
    if state == 4:
        raise CFUSyntaxError(line, col, "Expected closing quote at end of input")
    if state == 5:
        raise CFUSyntaxError(line, col, "Unfinished escape sequence at end of input")
    if state == 7:
        raise CFUSyntaxError(line, col, "Expected `=' at end of input")

    if state == 2:
        finish_token(True)
    elif state == 6:
        finish_token(True)

    return ts


def parse_list_pair_of_str_dependency_list_str(ts):
    """
    :param list(int, int, str, bool) ts: Token string
    :returns list(tuple(str, str, list(VersionConstraint)))
    """
    # Power set constructed DFA parser
    state = 1
    line = 0
    col = 0

    _list = []

    bp_name = None
    dep = None
    constraints = None
    constraint_type = None

    for line, col, token, is_literal in ts:
        if state == 1:
            if is_literal:
                bp_name = token
                state = 2

            elif token == "\n":
                state = 1

            else:
                raise CFUSyntaxError(line, col, "Expected literal or non-literal `\\n'")

        elif state == 2:
            if not is_literal and token == "->":
                state = 3

            else:
                raise CFUSyntaxError(line, col, "Expected non-literal `->'")

        elif state == 3:
            if is_literal:
                dep = token
                constraints = []
                state = 4

            else:
                raise CFUSyntaxError(line, col, "Expected literal")

        elif state == 4:
            if not is_literal and token == "\n":
                _list.append((bp_name, dep, constraints))
                state = 1

            elif not is_literal and token in ('<', '>', '>=', '<=', '!=', '==', '='):
                constraint_type = token
                state = 5

            else:
                raise CFUSyntaxError(line, col, "Expected non-literal from (< > <= >= == = \\n)")

        elif state == 5:
            if is_literal:
                try:
                    v = VersionNumber(token)
                except Exception as e:
                    raise CFUSyntaxError(line, col, "Invalid version number `%s': %s" %
                            (token, e))

                if constraint_type == '==':
                    constraint_type = '='

                constraints.append(VersionConstraint(constraint_type, v))
                state = 4

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

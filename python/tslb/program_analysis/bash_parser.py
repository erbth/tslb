"""
A very simple bash parser to parse bash scripts / extract certain information
from them.

This parser assumes that a bash script is a list of 'commands' ('command' are
like statements, a list of command is named 'list').

NOTE: This parser does probably not implement the bash language. It aims to
implement a language simple enough language which is close enough to bash s.t.
script dependencies etc. can be analyzed from its output. And it will only work
properly with well-formed shell scripts (those accepted by bash without syntax
errors).

The parser skips over a lot of constructs it does not fully implement.
"""
import re
import tslb.stack


def find_function_definitions(cmds):
    """
    Given a list of commands from `find_simple_commands` (or
    `simple_variable_substitution` resp.) extract the names of defined
    functions.

    :rtype: Set(str)
    """
    output = set()

    for cmd in cmds:
        if cmd.first_word:
            if cmd.first_word == 'function' and cmd.remainder:
                m = re.match(r'^([^{]*)', cmd.remainder[0])
                if m:
                    output.add(m[1])

            # Ok, this character set may be incomplete - but I trust it more
            # than blacklisting metacharacters etc.
            elif re.match(r'^[0-9a-zA-Z_:]+\s*\(\s*\)', cmd.first_word):
                output.add(re.match(r'^([0-9a-zA-Z_:]+)\s*\(', cmd.first_word)[1])

            elif cmd.remainder and cmd.remainder[0].startswith('('):
                output.add(cmd.first_word)

    return output


def simple_variable_substitution(cmds, include_loader=None):
    """
    Given a list of commands from `find_simple_commands` perform `variable
    substitution' on first words and included file paths.

    :param include_loader: A function that gets the path to an included file as
        argument and should return the files content or None, if the file could
        not be found.
    """
    output = []
    variables = {}
    loaded_files = set()

    def _expand(tmp):
        # Case 1: .*$name
        m = re.match(r'^[0-9a-zA-Z_]*(\$[0-9a-zA-Z_]+)', tmp)
        if m:
            tmp = tmp.replace(m[1], variables.get(m[1][1:], '').strip('"'))

        # Case 2: ${...} (simplified)
        for k, v in variables.items():
            tmp = tmp.replace('${' + k + '}', v)

        return tmp

    pos = 0
    while pos < len(cmds):
        cmd = cmds[pos]

        if cmd.variable_assignment:
            variables[cmd.variable_assignment[0]] = _expand(cmd.variable_assignment[1].strip('"'))

        if cmd.first_word in ('.', 'source') and cmd.remainder:
            tmp = _expand(cmd.remainder[0].strip('"'))

            new_remainder = ([tmp] if tmp else []) + cmd.remainder[1:]
            output.append(SimpleCommand(
                cmd.variable_assignment,
                cmd.first_word,
                new_remainder if new_remainder else None
            ))

            # Try to load the file.
            if include_loader and new_remainder and new_remainder[0] not in loaded_files:
                text = include_loader(new_remainder[0])
                loaded_files.add(new_remainder[0])

                if text:
                    # Parse script and insert its tokens instead of the
                    # include-command.
                    output.pop()
                    cmds = cmds[:pos] + find_simple_commands(text) + cmds[pos+1:]
                    pos -= 1

        elif cmd.first_word:
            had_quotes = cmd.first_word[0] == '"'
            tmp = cmd.first_word.strip('"')
            tmp = _expand(tmp)

            new_remainder = cmd.remainder if cmd.remainder else []

            tmp_stripped = tmp.strip()
            if not had_quotes and tmp_stripped:
                elems = tmp_stripped.split()
                tmp = elems[0]
                new_remainder = new_remainder + elems[1:]

            if cmd.variable_assignment or tmp:
                output.append(SimpleCommand(
                    cmd.variable_assignment,
                    tmp,
                    new_remainder if new_remainder else None
                ))

        else:
            output.append(cmd)

        pos += 1

    return output


def find_simple_commands(script):
    """
    Try to find all simple commands in bash terms

    :param str script: Script text
    :rtype: List(SimpleCommand)
    """
    return _find_simple_commands_tokens(_token_splitting(script))

def _find_simple_commands_tokens(tokens):
    stack = tslb.stack.stack()
    simple_commands = []

    # Try with a DPDA-like parser
    current = []
    def emit():
        nonlocal current
        if current:
            simple_commands.append(current)
            current = []

    for token in tokens:
        # Here Documents
        if not stack.empty and stack.top == '<<':
            stack.pop()
            end = token.strip('"').strip("'")
            stack.push('here-' + end)

        if not stack.empty and stack.top.startswith('here-'):
            if token == '\n' and len(current) >= 2 and \
                    current[-1] == stack.top[5:] and current[-2] == '\n':
                emit()
                stack.pop()

            else:
                current.append(token)

        elif current and current[-1] == '<' and token == '<':
            current.pop()
            current.append('<<')

            stack.push('<<')

        # Comments
        elif not stack.empty and stack.top == '#' and token != '\n':
            # Ignore line continuation in comment
            if token == '\\\n':
                stack.pop()
                emit()

        elif token.startswith('#'):
            stack.push('#')

        # Line continuations
        elif token == '\\\n':
            pass


        # If-then-else
        # Next follows a list or a 'then', 'elif', 'else' or 'fi.
        elif not stack.empty and stack.top == 'if' and token in ('then', 'elif', 'else', 'fi'):
            if token == 'fi':
                stack.pop()
            elif token == 'elif':
                current.append(token)

        elif token == 'if':
            stack.push(token)
            current.append(token)

        # Loops in general
        elif not stack.empty and stack.top == 'do' and token == 'done':
            stack.pop()

        # while / until
        # Next follows a list, a 'do', or 'done'
        elif not stack.empty and stack.top in ('while', 'until') and token == 'do':
            stack.pop()
            stack.push('do')

        elif token in ('while', 'until'):
            stack.push(token)
            current.append(token)

        # for ((...)) and for ... in
        # Next follows (( or a variable name and then 'in'.
        elif not stack.empty and stack.top == 'for' and token in ('in','('):
            stack.pop()
            stack.push('for' + token)
            current.append(token)

        elif not stack.empty and stack.top == 'for(' and token != 'do':
            current.append(token)

        elif not stack.empty and token == 'do' and stack.top in ('for(', 'forin'):
            stack.pop()
            stack.push('do')

        elif token == 'for':
            stack.push(token)
            current.append(token)

        # case
        elif not stack.empty and stack.top == 'case':
            if token == 'esac':
                stack.pop()

            if token == ')':
                stack.push('case)')

        elif not stack.empty and stack.top == 'case)' and token == ';':
            stack.pop()
            stack.push('case);');

        elif not stack.empty and stack.top == 'case);' and token == ';':
            stack.pop()

        elif token == 'case':
            stack.push(token)
            current.append(token)

        # select - like lists
        elif not stack.empty and stack.top == 'select' and token == 'do':
            stack.pop()
            stack.push('do')

        elif token == 'select':
            stack.push(token)
            current.append(token)


        # Lists
        elif token in ('\n', ';', '&', '|'):
            if token == '&' and current and current[-1] == '>':
                current.pop()
                current.append('>&')

            else:
                emit()

                if not stack.empty and stack.top == '#':
                    stack.pop()

        else:
            current.append(token)


    # Try to interpret simple commands
    output = []
    for cmd in simple_commands:
        # Recursively parse command substitutions. Command substitutions are
        # replaced by empty strings (would be by the command's stdout when run
        # by a shell).
        # Case 1: a token is a double-quoted word which contains a command
        # substitution
        def _process(word):
            nonlocal output
            if word.startswith('"') and word.endswith('"'):
                substs = re.findall(r'\$\((?:[\\]\)|[^)])*\)|`(?:[\\]`|[^`])*`', word)
                for subst in substs:
                    # Arithmetic expansion
                    if subst.startswith('$(('):
                        continue

                    word = word.replace(subst, '')
                    if subst.startswith('$('):
                        subst = subst[2:-1]
                    else:
                        subst = subst[1:-1]

                    output += _find_simple_commands_tokens(_token_splitting(subst + '\n'))

            return word

        cmd = [_process(word) for word in cmd]

        # Case 2: a command substitution is spread across multiple words
        _cmd = cmd
        cmd = []

        last = ''
        in_subst = None
        sub_cmd = []
        def emit():
            nonlocal sub_cmd, output
            if sub_cmd:
                output += _find_simple_commands_tokens(sub_cmd + ['\n'])
                sub_cmd = []

        for t in _cmd:
            if not t:
                continue

            if in_subst == '$(' and t == ')':
                emit()
                in_subst = None
                cmd.append('')

            elif t == '(' and last.endswith('$'):
                if cmd:
                    cmd.pop()

                if last != '$':
                    cmd.append(last[:-1])
                in_subst = '$('

            elif t[0] not in ('"', "'") and re.match(r'`|.*[^\\]`', t):
                # Join words until the number of '`' is even and then perform
                # command substitution
                in_subst = '`'
                if not sub_cmd:
                    sub_cmd.append(t)
                else:
                    sub_cmd[0] += ' ' + t

                if len(re.findall(r'^`|[^\\]`', sub_cmd[0])) % 2 == 0:
                    substs = re.findall(r'`(?:[\\]`|[^`])*`', sub_cmd[0])
                    for subst in substs:
                        sub_cmd[0] = sub_cmd[0].replace(subst, '')
                        subst = subst[1:-1]
                        output += _find_simple_commands_tokens(_token_splitting(subst + '\n'))

                    in_subst = None
                    cmd.append(sub_cmd[0])
                    sub_cmd = []

            elif in_subst == '$(' and t == '(':
                # Arithmetic expansion
                cmd.append('$')
                cmd.append('(')
                cmd.append('(')
                in_subst = None
                sub_cmd = []

            elif in_subst == '$(':
                sub_cmd.append(t)

            elif in_subst == '`':
                sub_cmd[0] += ' ' + t

            else:
                cmd.append(t)

            last = t


        # If the script is too complex to parse completely or not well-formed,
        # cmd might be empty here. Skip processing in these cases.
        if not cmd:
            continue


        # Skip control flow constructs that do not use lists
        if cmd[0] in ('case', 'select', 'for'):
            continue

        # Recursively parse lists
        if cmd[0] in ('while', 'until', 'if', 'elif'):
            r = cmd[1:]
            l = []

            def emit():
                nonlocal l, output
                if l:
                    l.append('\n')
                    output += _find_simple_commands_tokens(l)
                    l = []

            def shift():
                nonlocal r
                r = r[1:]

            while r:
                if r[0] == '!':
                    emit()
                    shift()

                elif r[0] in ('&&', '||'):
                    emit()
                    shift()

                else:
                    l.append(r[0])
                    shift()

            emit()

            continue

        # Regular command processing
        v = None
        fw = None
        r = None

        i = 0
        if '=' in cmd[0]:
            p = cmd[0].split('=')
            v = (p[0], '='.join(p[1:]))
            i += 1

        if i < len(cmd):
            fw = cmd[i]
            i += 1

            if i < len(cmd):
                r = cmd[i:]

        output.append(SimpleCommand(v, fw, r))

    return output


def _token_splitting(script):
    tokens = []

    stack = tslb.stack.stack()
    current = ''
    def emit():
        nonlocal current
        if current:
            tokens.append(current)
            current = ''

    last = ''
    for c in script:
        if not stack.empty and stack.top in ('&', '|') and c != stack.top:
            current += stack.pop()
            emit()

        if not stack.empty and stack.top in ('&', '|') and c == stack.top:
            current += c + c
            stack.pop()
            emit()

        # Ignore comments
        elif not stack.empty and stack.top == '#':
            if c == '\n':
                stack.pop()

        elif c == '#':
            stack.push('#')

        # Quoting single characters: backslash takes the next character literal
        # or is the line continuation \\\n.
        elif last == '\\':
            if c == '\n':
                emit()
                tokens.append('\\\n')
                emit()

            else:
                current += '\\' + c

        elif not stack.empty and stack.top in ('"', "'"):
            current += c
            if c == stack.top:
                stack.pop()

        elif c in ('&', '|'):
            stack.push(c)

        elif is_metacharacter(c):
            emit()
            if not is_whitespace(c):
                tokens.append(c)

        elif c in ('"', "'"):
            current += c
            stack.push(c)

        # Backslash has a meaning on the following character.
        elif c == '\\':
            pass

        else:
            current += c

        last = c

    return tokens


def is_whitespace(c):
    return c in (' ', '\t', '\r')

def is_metacharacter(c):
    """
    Metacharacters cause word breaks.
    """
    return c in {'|', '&', ';', '(', ')', '<', '>', ' ', '\t', '\n'}

def is_builtin(word):
    """
    Identify shell builtins
    """
    return word in {
        ":", ".", "alias", "bg", "bind", "break", "builtin", "caller", "cd",
        "command", "complete", "compopt", "continue", "declare", "typeset",
        "dirs ", "disown", "echo", "enable", "eval", "exec", "exit", "export",
        "false", "fc", "fg", "getopts", "hash", "help", "history ", "jobs",
        "kill", "let", "local", "logout", "mapfile", "readarray", "popd",
        "printf", "pushd", "pwd", "read", "readonly", "return", "set", "shift",
        "shopt", "suspend", "test", "true", "[", "times", "trap", "type",
        "ulimit", "umask", "unalias", "unset", "wait"
    }

def is_reserved(word):
    """
    Reserved words
    """
    return word in {
        "!", "case", "", "coproc", "", "do", "done", "elif", "else", "esac",
        "fi", "for", "function", "if", "in", "select", "then", "until",
        "while", "{", "}", "time", "[[", "]]"
    }


class SimpleCommand:
    """
    This class represents a simple command. Everything may be None, but at
    least `variable_assignment` or `first_word` must be present.

    `SimpleCommand`s are immutable.

    :param variable_assignment: A tuple (<variable name>, value)
    :param remainder: A list of the remaining tokens, includes redirections,
        here docs, etc. (note that these are not only `words' in bash terms...
    """
    def __init__(self, variable_assignment, first_word, remainder):
        self._variable_assignment = variable_assignment
        self._first_word = first_word
        self._remainder = remainder

        if not first_word and not variable_assignment:
            raise ValueError("At least one of `first_word` and "
                    "`variable_assignment` must not be empty.")

        if variable_assignment and (
                not isinstance(variable_assignment, tuple) or \
                len(variable_assignment) != 2):
            raise TypeError("`variable_assignment` must be a tuple of length 2.")

        if remainder and not isinstance(remainder, list):
            raise TypeError("`remainder` must be a list.")

    @property
    def variable_assignment(self):
        return self._variable_assignment

    @property
    def first_word(self):
        return self._first_word

    @property
    def remainder(self):
        return self._remainder

    def __str__(self):
        s = []
        if self._variable_assignment:
            s.append("%s=%s" % self._variable_assignment)

        if self._first_word:
            s.append(self._first_word)

        if self._remainder:
            s.append(str(self._remainder))

        return ' '.join(s)

"""
Tools for analyzing bash scripts
"""
import re
from . import bash_parser


def determine_required_programs(script, include_loader=None):
    """
    Determine which external programs are called by a bash script.

    :param str script: The script text as string.
    :param include_loader: A function that gets the path to an included file as
        argument and should return the files content or None, if the file could
        not be found.
    :returns Set(str): A set of programs / paths to programs as they appear in
        the script.
    """
    programs = set()

    cmds = bash_parser.find_simple_commands(script)
    cmds = bash_parser.simple_variable_substitution(cmds, include_loader)
    functions = bash_parser.find_function_definitions(cmds)

    for cmd in cmds:
        if not cmd.first_word or bash_parser.is_builtin(cmd.first_word):
            continue

        # Ignore additional words left from constructs the parser did not fully
        # understand
        if bash_parser.is_metacharacter(cmd.first_word) or \
                bash_parser.is_reserved(cmd.first_word) or \
                cmd.first_word in ('||', '&&', '{', '}', '[', ']'):
            continue

        # Skip functions
        if cmd.first_word in functions:
            continue

        # Skip other strange things...
        if not re.match(r'^[0-9a-zA-Z._/-]+$', cmd.first_word):
            continue

        programs.add(cmd.first_word)

    return programs

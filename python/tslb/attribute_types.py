"""
A central place for functions verifying source- / binary packages' attribute
types.

The functions defined here raise InvalidAttributeType exceptions with
descriptions about the type mismatch on error.
"""

def ensure_list_of_strings(val):
    if not isinstance(val, list):
        raise InvalidAttributeTypeDiff("List(str)", type(val))

    for e in val:
        if not isinstance(e, str):
            raise InvalidAttributeType("Should be `List(str)', has element of type `%s'." % type(e))

def ensure_list_of_tuples_of_strings_and_strings_or_lists_of_strings(val):
    type_ = "List(Tuple(str, str|List(str)))"

    if not isinstance(val, list):
        raise InvalidAttributeTypeDiff(type_, type(val))

    for e in val:
        if not isinstance(e, tuple):
            raise InvalidAttributeTypeDiff(type_, "List(%s)" % type(e))

        if len(e) != 2 or not isinstance(e[0], str):
            raise InvalidAttributeTypeDiff(type_, "List(Typle(...))")

        if not isinstance(e[1], str) and not isinstance(e[1], list):
            raise InvalidAttributeTypeDiff(type_, "List(Typle(str, ...))")

        if isinstance(e[1], list):
            for e2 in e[1]:
                if not isinstance(e2, str):
                    raise InvalidAttributeTypeDiff(type_, "List(Typle(str, List(...)))")


# Aliases for different attributes
ensure_package_manager_trigger_list = ensure_list_of_strings
ensure_package_manager_trigger_list_sp = ensure_list_of_tuples_of_strings_and_strings_or_lists_of_strings

ensure_remove_rdeps = ensure_list_of_tuples_of_strings_and_strings_or_lists_of_strings
ensure_disable_dependency_analyzer_for = ensure_list_of_strings
ensure_enable_dependency_analyzer_for = ensure_disable_dependency_analyzer_for
ensure_strip_skip_paths = ensure_list_of_strings

ensure_packaging_hints = ensure_list_of_tuples_of_strings_and_strings_or_lists_of_strings


#******************************** Exceptions **********************************
class InvalidAttributeType(Exception):
    """
    In the simplest case, :param msg: is just the type.

    :param str attr: Can be used to qualify the attribute when re-raising the
        exception. :param msg: must be then the original exception.
    """
    def __init__(self, msg, attr=None):
        if isinstance(msg, InvalidAttributeType):
            if attr is not None:
                super().__init__("Attribute `%s': %s" % (attr, msg))
            else:
                super().__init__(str(msg))
        else:
            super().__init__("Invalid attribute type: %s" % msg)

class InvalidAttributeTypeDiff(InvalidAttributeType):
    def __init__(self, should, is_):
        super().__init__("Should be `%s', is `%s'." % (should, is_))

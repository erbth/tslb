def edit_object_str(string):
    pass


def edit_object(obj, rw):
    """
    Display an editor for the given object on stdout.

    :param obj: The object to edit
    :param bool rw: True if the object should be editable, False if a read-only
        view shall be presented.
    :returns: The new (possibly changed) object
    :raises UnsupportedObject: if the object is not supported.
    """
    if isinstance(obj, str):
        return edit_object_str(obj)
    else:
        raise UnsupportedObject(type(obj))


class UnsupportedObject(Exception):
    def __init__(self, _type):
        super().__init__("Unsupported object of type `%s'." % _type)

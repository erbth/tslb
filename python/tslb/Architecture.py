i386 = 1
amd64 = 2

architectures = {
        i386 : 'i386',
        amd64 : 'amd64'
}

architectures_reverse = {
        'i386': i386,
        'amd64': amd64
}


def to_int(param):
    """
    Converts an acrchitecture in int or str format to the int representation.

    :param param: int or str arch representation
    :type param: int or str
    :returns: The arch in int representation
    :rtype: int
    """
    if isinstance(param, int):
        return param
    elif isinstance(param, str):
        return architectures_reverse[param]
    else:
        raise TypeError


def to_str(param):
    """
    Converts an architecture in int or str format to the str representation.

    :param param: int or str arch representation
    :type param: int or str
    :returns: The arch in str representation
    :rtype: str
    :raises TypeError, ValueError:
    """
    if isinstance(param, int):
        try:
            return architectures[param]
        except KeyError as exc:
            raise ValueError("Invalid architecture") from exc

    elif isinstance(param, str):
        if param not in architectures_reverse:
            raise ValueError("Invalid architecture")

        return param
    else:
        raise TypeError

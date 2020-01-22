from tslb.stream import stream, StreamNoDataError
import logging

def create(msgid):
    s = stream()
    s.write_uint32(msgid)
    s.write_uint32(0)
    return s

def update_length(s):
    pos = s.tell()
    s.seek_set(4)
    s.write_uint32(len(s) - 8)
    s.seek_set(pos)
    return s

def create_build_master_update(t=None):
    """
    :param t: (name, yamb_addr, seems_dead) or None.
    """
    s = create(0x00100001)

    if t is not None:
        name, yamb_addr, seems_dead = t
        s.write_str_with_len(name)
        s.write_uint32(yamb_addr)
        s.write_uint8(1 if seems_dead else 0)
        update_length(s)

    return s


# Receiving messages
def contains_full(data):
    """
    :type data: tslb.stream.stream
    :returns: The full length (>= 8) if a message is contained, None else.
    """
    if len(data) >= 8:
        pos = data.tell()
        data.seek_set(4)
        l = data.read_uint32() + 8
        data.seek_set(pos)

        if len(data) >= l:
            return l

    return None

def parse(data):
    """
    Side effects: the input stream is read until the begin of the payload.

    :param data: Must include a full message.
    :type data: tslb.stream.stream
    :returns: (msgid, payload length)
    """
    msgid = data.read_uint32()
    length = data.read_uint32()

    return (msgid, length)

def parse_get_node_state(date):
    """
    Parses a get_node_state message. Raises a ParseError in case of failure.

    :param data: The message, seek'd to the begin of the payload.
    :param length: The length of the payload.
    :returns: name (identity) of node
    """
    try:
        length = data.read_uint32()
        return data.read_bytearray(length).decode('utf8')

    except StreamNoDataError:
        raise TooShortError('get_node_state')


class ParseError(Exception):
    def __init__(self, msg):
        super().__init__("Failed to parse message: %s" % msg)

class TooShortError(ParseError):
    def __init__(self, msgname):
        super().__init__("Too short %s message." % msgname)

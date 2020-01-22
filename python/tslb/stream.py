class stream(object):
    def __init__(self):
        self.buffer = bytearray()
        self.pos = 0

    def read_uint8(self):
        if self.remaining_length() < 1:
            raise StreamNoDataError

        v = self.buffer[self.pos]
        self.pos += 1
        return v

    def read_uint16(self):
        if self.remaining_length() < 2:
            raise StreamNoDataError

        v = self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1

        return v

    def read_uint32(self):
        if self.remaining_length() < 4:
            raise StreamNoDataError

        v = self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1

        return v

    def read_uint64(self):
        if self.remaining_length() < 8:
            raise StreamNoDataError

        v = self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1
        v = v << 8 | self.buffer[self.pos]
        self.pos += 1

        return v

    def read_bytearray(self, count):
        if self.pos + count > len(self):
            raise StreamNoDataError

        data = self.buffer[self.pos:self.pos+count]
        self.pos += count
        return data


    def write_uint8(self, v):
        missing = 1 - self.remaining_length()
        if missing > 0:
            self.buffer.extend(b'0'*missing)

        self.buffer[self.pos] = v
        self.pos += 1

    def write_uint16(self, v):
        missing = 2 - self.remaining_length()
        if missing > 0:
            self.buffer.extend(b'0'*missing)

        self.buffer[self.pos+1] = v & 0xff
        v = v >> 8
        self.buffer[self.pos] = v & 0xff

        self.pos += 2

    def write_uint32(self, v):
        missing = 4 - self.remaining_length()
        if missing > 0:
            self.buffer.extend(b'0'*missing)

        self.buffer[self.pos+3] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+2] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+1] = v & 0xff
        v = v >> 8
        self.buffer[self.pos] = v & 0xff

        self.pos += 4

    def write_uint64(self, v):
        missing = 8 - self.remaining_length()
        if missing > 0:
            self.buffer.extend(b'0'*missing)

        self.buffer[self.pos+7] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+6] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+5] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+4] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+3] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+2] = v & 0xff
        v = v >> 8
        self.buffer[self.pos+1] = v & 0xff
        v = v >> 8
        self.buffer[self.pos] = v & 0xff

        self.pos += 8

    def write_bytes(self, o):
        if isinstance(o, bytes) or isinstance(o, bytearray):
            missing = len(o) - self.remaining_length()

            if missing > 0:
                present = len(o) - missing

                if present > 0:
                    self.buffer[self.pos:self.pos+present] = o[0:present]

                self.buffer.extend(o[present:])

            else:
                self.buffer[self.pos:self.pos+len(o)] = o

            self.pos += len(o)

        else:
            raise TypeError

    def write_str(self, s):
        self.write_bytes(s.encode('utf8'))

    def write_str_with_len(self, s):
        s = s.encode('utf8')
        self.write_uint32(len(s))
        self.write_bytes(s)


    def tell(self):
        return self.pos

    def __len__(self):
        return self.buffer.__len__()

    def remaining_length(self):
        return len(self) - self.pos

    def seek_set(self, pos):
        if pos < 0 or pos > len(self):
            raise StreamOutOfBoundsError

        self.pos = pos

    def seek_cur(self, delta):
        new_pos = self.pos + delta

        if new_pos < 0 or new_pos > len(self):
            raise StreamOutOfBoundsError

        self.pos = new_pos


    def pop(self, count):
        if count > len(self):
            raise StreamNoDataError

        s = self.__class__()
        s.write_bytes(self.buffer[0:count])
        s.seek_set(0)

        del self.buffer[0:count]

        if self.pos < count:
            self.pos = 0
        else:
            self.pos -= count

        return s


    def __str__(self):
        return ':'.join(["{:02x}".format(a) for a in self.buffer])

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))

class StreamNoDataError(Exception):
    def __init__(self):
        super().__init__("Not enough data in stream.")

class StreamOutOfBoundsError(Exception):
    def __init__(self):
        super().__init__("Out of bounds of stream.")

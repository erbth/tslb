from array import array
from pytest import mark, raises
from tslb.buffers import ConsoleBufferFixedSize
import math
import secrets


class TestConsoleBufferFixedSize:
    def test__init__(self):
        b = ConsoleBufferFixedSize()

        assert b._buf_capacity == 10 * 1024 * 1024 + 1
        assert len(b.data) == b._buf_capacity
        assert b.begin == 0
        assert b.end == 0

        b = ConsoleBufferFixedSize(1000)

        assert b._buf_capacity == 1001
        assert len(b.data) == b._buf_capacity
        assert b.begin == 0
        assert b.end == 0


    def test_empty(self):
        b = ConsoleBufferFixedSize()
        assert b.empty

        b.end = 1
        assert not b.empty


    def test_capacity(self):
        b = ConsoleBufferFixedSize(1000)
        assert b.capacity == 1000


    def test_size(self):
        b = ConsoleBufferFixedSize(1000)
        assert b.size == 0

        b.end = 4
        b.data[0:4] = bytearray(b'test')

        assert b.size == 4

        b.begin = 4
        b.end = 0
        assert b.size == 997

        b.begin = 4
        b.end = 1
        assert b.size == 998


    def test_free(self):
        b = ConsoleBufferFixedSize(1000)
        assert b.free == 1000

        b.end = 4
        b.data[0:4] = bytearray(b'test')

        assert b.free == 996

        b.begin = 4
        b.end = 0
        assert b.free == 3

        b.begin = 4
        b.end = 1
        assert b.free == 2


    def test_append_data_too_large(self):
        b = ConsoleBufferFixedSize(1000)
        b.append_data(secrets.token_bytes(1000))

        b = ConsoleBufferFixedSize(1000)

        with raises(ValueError, match=r'Data too large for buffer\.'):
            b.append_data(secrets.token_bytes(1001))


    def test_append_data_basic(self):
        b = ConsoleBufferFixedSize()
        assert b.empty

        b.append_data(b'Hello, World!\n')
        assert not b.empty

        assert b.begin == 0
        assert b.end == 14
        assert b.data[0:14] == b'Hello, World!\n'


    def test_append_more_data(self):
        b = ConsoleBufferFixedSize()

        c1 = secrets.token_bytes(math.floor(b.capacity / 2) - 4)
        c2 = secrets.token_bytes(math.floor(b.capacity / 2) - 3)
        c3 = secrets.token_bytes(b.capacity - len(c2) - len(c1))
        c4 = secrets.token_bytes(1)
        c5 = secrets.token_bytes(math.floor(b.capacity / 2) - 2)
        c6 = secrets.token_bytes(math.floor(b.capacity / 2) - 100)
        c7 = secrets.token_bytes(math.floor(b.capacity / 2) - 99)

        b.append_data(c1)

        assert b.begin == 0
        assert b.end == len(c1)
        assert b.data[0:len(c1)] == c1


        b.append_data(c2)

        assert b.begin == 0
        assert b.end == len(c1) + len(c2)
        assert b.data[0:len(c1) + len(c2)] == c1 + c2


        b.append_data(c3)

        assert b.begin == 0
        assert b.end == b.capacity
        assert b.data[:-1] == c1 + c2 + c3
        assert b.size == b.capacity
        assert b.free == 0


        b.append_data(c4)

        assert b.begin == 1
        assert b.end == 0
        assert b.data == c1 + c2 + c3 + c4
        assert b.size == b.capacity
        assert b.free == 0


        b.append_data(c5)

        assert b.begin == 1 + len(c5)
        assert b.end == len(c5)
        assert b.data == c5 + (c1 + c2 + c3 + c4)[len(c5):]
        assert b.size == b.capacity
        assert b.free == 0


        b.append_data(c6)

        assert b.begin == 1 + len(c5) + len(c6)
        assert b.end == len(c5) + len(c6)
        assert b.data == c5 + c6 + (c1 + c2 + c3 + c4)[len(c5) + len(c6):]
        assert b.size == b.capacity
        assert b.free == 0


        b.append_data(c7)

        assert b.begin == len(c7) - (b._buf_capacity - 1 - len(c5) - len(c6))
        assert b.end == len(c7) - (b._buf_capacity - 1 - len(c5) - len(c6)) - 1
        assert b.data == c7[len(c7) - b.end:] + c5[b.end:] + c6 + c7[:len(c7) - b.end]
        assert b.size == b.capacity
        assert b.free == 0


    def test_size_2(self):
        b = ConsoleBufferFixedSize()
        assert b.size == 0
        b.append_data(b'Hello, World!\n')
        assert b.size == 14

        c = secrets.token_bytes(math.floor(b.capacity / 2) - 3)

        b.append_data(c)
        assert b.size == len(c) + 14

        b.append_data(c)
        assert b.size == b.capacity

        b.append_data(c)
        assert b.size == b.capacity


    def test_read_data(self):
        b = ConsoleBufferFixedSize()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c3 = secrets.token_bytes(b.capacity - len(c2) - len(c1))
        c4 = secrets.token_bytes(1)
        c5 = secrets.token_bytes(math.floor(b.capacity / 2) - 1)

        # Empty
        assert b.read_data(1) == b''

        # One item
        b.append_data(c1)

        assert b.read_data(0) == b''
        assert b.read_data(1) == c1[-1:]
        assert b.read_data(len(c1) - 1) == c1[1:]
        assert b.read_data(len(c1)) == c1
        assert b.read_data(len(c1) + 100) == c1
        assert b.read_data(-1) == c1


        # Two items
        b.append_data(c2)

        assert b.read_data(1) == c2[-1:]
        assert b.read_data(len(c2)) == c2
        assert b.read_data(-1) == c1 + c2


        # Almost wrapped around
        b.append_data(c3)

        assert b.read_data(1) == c3[-1:]
        assert b.read_data(-1) == c1 + c2 + c3


        # Wrap around
        b.append_data(c4)

        assert b.read_data(1) == c4
        assert b.read_data(2) == c3[-1:] + c4
        assert b.read_data(len(c3) + 1) == c3 + c4
        assert b.read_data(-1) == c1[1:] + c2 + c3 + c4


        # Continue after wrap around
        b.append_data(c5)

        assert b.read_data(-1) == (c1 + c2 + c3 + c4 + c5)[-b.capacity:]


    def test_clear(self):
        b = ConsoleBufferFixedSize()
        b.append_data(b'Hello, World!\n')

        assert b.size == 14
        assert b.read_data(-1) == b'Hello, World!\n'

        b.clear()
        assert b.size == 0
        assert b.read_data(-1) == b''

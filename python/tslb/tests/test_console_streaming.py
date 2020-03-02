from array import array
from pytest import mark, raises
from tslb import console_streaming as cs
import math
import secrets


def test_split_into_chunks():
    for max_size, max_size_set in [(524288, None), (1024 * 1024, 1024 * 1024)]:
        tds = [
            secrets.token_bytes(math.floor(max_size / 10)),
            secrets.token_bytes(max_size),
            secrets.token_bytes(max_size + 1),
            secrets.token_bytes(max_size * 3),
            secrets.token_bytes(max_size * 3 + 1),
            secrets.token_bytes(max_size * 3 - 1)
            ]

        kwargs = {}
        if max_size_set is not None:
            kwargs['max_chunk_size'] = max_size_set

        rs = [cs.split_into_chunks(d, **kwargs) for d in tds]

        assert rs[0] == [tds[0]]
        assert rs[1] == [tds[1]]
        assert rs[2] == [tds[2][0:max_size], tds[2][max_size:]]

        assert rs[3] == [tds[3][0:max_size], tds[3][max_size:max_size*2],
            tds[3][max_size*2:]]

        assert rs[4] == [tds[4][0:max_size], tds[4][max_size:max_size*2],
            tds[4][max_size*2:max_size*3], tds[4][max_size*3:]]

        assert rs[5] == [tds[5][0:max_size], tds[5][max_size:max_size*2],
            tds[5][max_size*2:]]


class TestBuffer:
    def test_empty(self):
        b = cs.Buffer()
        assert b.empty

        b.mdstart = 0
        b.mdend = 0
        assert not b.empty


    def test_size(self):
        b = cs.Buffer()
        assert b.size == 0

        b.mdstart = 0
        b.mdend = 0
        b.mdmarks[0] = 3343
        b.mdpointers[0] = 0
        b.data = bytearray(b'test')
        b.dend = 4

        assert b.size == 4


    def test_first_last_mark(self):
        b = cs.Buffer()
        assert b.first_mark == None
        assert b.last_mark == None

        b.mdstart = 0
        b.mdend = 0
        b.mdmarks[0] = 3343

        assert b.first_mark == 3343
        assert b.last_mark == 3343

        b.mdmarks.append(1234)
        b.mdend = 1

        assert b.first_mark == 3343
        assert b.last_mark == 1234


    def test_append_chunk_basic(self):
        b = cs.Buffer()
        assert b.empty

        assert b.append_chunk(b'Hello, World!\n') == 1
        assert not b.empty

        assert b.mdstart == 0
        assert b.mdend == 0
        assert b.mdmarks == array('L', [1])
        assert b.mdpointers == array('L', [0])
        assert b.dend == 14


    def test_append_chunk_multiple(self):
        b = cs.Buffer()
        assert b.empty

        c1 = secrets.token_bytes(math.floor(b.capacity / 4))
        c2 = secrets.token_bytes(math.floor(b.capacity / 4) - 1)
        c3 = secrets.token_bytes(math.floor(b.capacity / 4) - 2)
        c4 = b'test'

        assert b.append_chunk(c1) == 1
        assert not b.empty

        assert b.data[0:len(c1)] == c1
        assert b.dend == len(c1)
        assert b.mdstart == 0
        assert b.mdend == 0
        assert b.mdmarks[0:1] == array('L', [1])
        assert b.mdpointers[0:1] == array('L', [0])
        assert len(b.mdmarks) == 1
        assert b.size == len(c1)


        assert b.append_chunk(c2) == 2
        assert not b.empty

        assert b.mdstart == 0
        assert b.mdend == 1
        assert b.mdmarks[0:2] == array('L', [1, 2])
        assert b.mdpointers[0:2] == array('L', [0, len(c1)])
        assert b.dend == len(c1) + len(c2)
        assert b.data[0:b.size] == c1 + c2
        assert len(b.mdmarks) == 2
        assert b.size == len(c1) + len(c2)


        assert b.append_chunk(c3) == 3
        assert not b.empty

        assert b.data[0:b.size] == c1 + c2 + c3
        assert b.dend == len(c1) + len(c2) + len(c3)
        assert b.mdstart == 0
        assert b.mdend == 2
        assert b.mdmarks[0:3] == array('L', [1, 2, 3])
        assert b.mdpointers[0:3] == array('L', [0, len(c1), len(c1) + len(c2)])
        assert len(b.mdmarks) == 3
        assert b.size == len(c1) + len(c2) + len(c3)


        assert b.append_chunk(c4) == 4
        assert not b.empty

        assert b.data[0:b.size] == c1 + c2 + c3 + c4
        assert b.dend == len(c1) + len(c2) + len(c3) + len(c4)
        assert b.mdstart == 0
        assert b.mdend == 3
        assert b.mdmarks[0:4] == array('L', [1, 2, 3, 4])
        assert b.mdpointers[0:4] == array('L', [0, len(c1), len(c1) + len(c2), len(c1) + len(c2) + len(c3)])
        assert len(b.mdmarks) == 5
        assert b.size == len(c1) + len(c2) + len(c3) + len(c4)


    def test_append_chunk_wrap_around(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 2) - 3)
        c2 = secrets.token_bytes(math.floor(b.capacity / 2) - 2)
        c3 = secrets.token_bytes(math.floor(b.capacity / 2) - 1)

        assert b.append_chunk(c1) == 1
        assert b.append_chunk(c2) == 2
        assert b.append_chunk(c3) == 3

        assert not b.empty
        assert b.size == len(c2) + len(c3)

        assert b.mdstart == 1
        assert b.mdend == 0
        assert len(b.mdmarks) == 2
        assert b.mdmarks[0:2] == array('L', [3, 2])
        assert b.mdpointers[0:2] == array('L', [len(c1) + len(c2), len(c1)])

        assert b.dend == len(c3) - (b.capacity - len(c1) - len(c2))
        assert b.data[len(c1):] == c2 + c3[0:b.capacity - len(c1) - len(c2)]
        assert b.data[0:b.dend] == c3[b.capacity - len(c1) - len(c2):]


        assert b.append_chunk(c1) == 4

        assert not b.empty
        assert b.size == len(c3) + len(c1)

        assert b.mdstart == 0
        assert b.mdend == 1
        assert len(b.mdmarks) == 2
        assert b.mdmarks[0:2] == array('L', [3, 4])
        assert b.mdpointers[0:2] == array('L', [len(c1) + len(c2), len(c3) - (b.capacity - len(c1) - len(c2))])

        assert b.dend == len(c3) - (b.capacity - len(c1) - len(c2)) + len(c1)
        assert b.data[len(c1) + len(c2):] == c3[0:b.capacity - len(c1) - len(c2)]


    def test_size_2(self):
        b = cs.Buffer()
        assert b.size == 0
        b.append_chunk(b'Hello, World!\n')
        assert b.size == 14

        c = secrets.token_bytes(math.floor(b.capacity / 2) - 3)

        b.append_chunk(c)
        assert b.size == len(c) + 14

        b.append_chunk(c)
        assert b.size == len(c) * 2


    def test__find_mark_index(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c3 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c4 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c5 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)

        # Empty
        assert b._find_mark_index(1) is None

        # One item
        assert b.append_chunk(c1) == 1

        assert b._find_mark_index(1) == 0
        assert b._find_mark_index(2) == None

        # Two items
        assert b.append_chunk(c2) == 2

        assert b._find_mark_index(1) == 0
        assert b._find_mark_index(2) == 1
        assert b._find_mark_index(3) == None

        # Three items
        assert b.append_chunk(c3) == 3

        assert b._find_mark_index(1) == 0
        assert b._find_mark_index(2) == 1
        assert b._find_mark_index(3) == 2
        assert b._find_mark_index(4) == None

        # Wrap around
        assert b.append_chunk(c4) == 4

        assert b._find_mark_index(1) == None
        assert b._find_mark_index(2) == 1
        assert b._find_mark_index(3) == 2
        assert b._find_mark_index(4) == 0
        assert b._find_mark_index(5) == None

        # Continue after wrap around
        assert b.append_chunk(c5) == 5

        assert b._find_mark_index(1) == None
        assert b._find_mark_index(2) == None
        assert b._find_mark_index(3) == 2
        assert b._find_mark_index(4) == 0
        assert b._find_mark_index(5) == 1
        assert b._find_mark_index(6) == None


    def test_get_chunk_invalid_input(self):
        b = cs.Buffer()

        with raises(ValueError, match="marks -infinity and now not allowed."):
            b.get_chunk(0)

        with raises(ValueError, match="marks -infinity and now not allowed."):
            b.get_chunk(0xffffffff)


        assert b.get_chunk(1) is None
        assert b.get_chunk(0xfffffffe) is None


    def test_get_chunk(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c3 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c4 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c5 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)

        # Empty
        assert b.get_chunk(1) is None

        # One item
        assert b.append_chunk(c1) == 1

        assert b.get_chunk(1) == c1
        assert b.get_chunk(2) == None

        # Two items
        assert b.append_chunk(c2) == 2

        assert b.get_chunk(1) == c1
        assert b.get_chunk(2) == c2
        assert b.get_chunk(3) == None

        # Three items
        assert b.append_chunk(c3) == 3

        assert b.get_chunk(1) == c1
        assert b.get_chunk(2) == c2
        assert b.get_chunk(3) == c3
        assert b.get_chunk(4) == None

        # Wrap around
        assert b.append_chunk(c4) == 4

        assert b.get_chunk(1) == None
        assert b.get_chunk(2) == c2
        assert b.get_chunk(3) == c3
        assert b.get_chunk(4) == c4
        assert b.get_chunk(5) == None

        # Continue after wrap around
        assert b.append_chunk(c5) == 5

        assert b.get_chunk(1) == None
        assert b.get_chunk(2) == None
        assert b.get_chunk(3) == c3
        assert b.get_chunk(4) == c4
        assert b.get_chunk(5) == c5
        assert b.get_chunk(6) == None


    def test_get_chunks_not_in_buffer(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)

        # Empty
        with raises(ValueError, match="mstart not in the buffer."):
            b.get_chunks(1, 1)

        # One element
        assert b.append_chunk(c1) == 1

        with raises(ValueError, match="mend not in the buffer."):
            b.get_chunks(1, 2)

        with raises(ValueError, match="mstart not in the buffer."):
            b.get_chunks(2, 2)


    def test_get_chunks_invalid_order(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c3 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c4 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)

        assert b.append_chunk(c1) == 1
        assert b.append_chunk(c2) == 2

        with raises(ValueError, match=r"mstart > mend \(1\)"):
            b.get_chunks(2,1)

        assert b.append_chunk(c3) == 3
        assert b.append_chunk(c4) == 4

        with raises(ValueError, match=r"mstart > mend \(2\)"):
            b.get_chunks(3,2)

        with raises(ValueError, match=r"mstart > mend \(4\)"):
            b.get_chunks(4,3)

        assert b.append_chunk(c1) == 5

        with raises(ValueError, match=r"mstart > mend \(3\)"):
            b.get_chunks(5,4)


    def test_get_chunks_explicit(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 2)
        c3 = secrets.token_bytes(math.floor(b.capacity / 3) - 3)
        c4 = secrets.token_bytes(math.floor(b.capacity / 3) - 4)
        c5 = secrets.token_bytes(math.floor(b.capacity / 3) - 5)

        # One item
        assert b.append_chunk(c1) == 1

        assert b.get_chunks(1, 1) == ([(1, 0)], c1)

        # Two items
        assert b.append_chunk(c2) == 2

        assert b.get_chunks(1,1) == ([(1, 0)], c1)
        assert b.get_chunks(2,2) == ([(2, 0)], c2)
        assert b.get_chunks(1,2) == ([(1,0), (2, len(c1))], c1 + c2)

        # Three items
        assert b.append_chunk(c3) == 3

        assert b.get_chunks(1,1) == ([(1, 0)], c1)
        assert b.get_chunks(2,2) == ([(2, 0)], c2)
        assert b.get_chunks(3,3) == ([(3, 0)], c3)
        assert b.get_chunks(1,2) == ([(1,0), (2, len(c1))], c1 + c2)
        assert b.get_chunks(2,3) == ([(2,0), (3, len(c2))], c2 + c3)
        assert b.get_chunks(1,3) == ([(1,0), (2, len(c1)), (3, len(c1) + len(c2))], c1 + c2 + c3)

        # Wrap around
        assert b.append_chunk(c4) == 4

        assert b.get_chunks(2,2) == ([(2, 0)], c2)
        assert b.get_chunks(3,3) == ([(3, 0)], c3)
        assert b.get_chunks(4,4) == ([(4, 0)], c4)
        assert b.get_chunks(2,3) == ([(2,0), (3, len(c2))], c2 + c3)
        assert b.get_chunks(3,4) == ([(3,0), (4, len(c3))], c3 + c4)
        assert b.get_chunks(2,4) == ([(2,0), (3, len(c2)), (4, len(c2) + len(c3))], c2 + c3 + c4)

        # Continue after wrap around
        assert b.append_chunk(c5) == 5

        assert b.get_chunks(5,5) == ([(5, 0)], c5)
        assert b.get_chunks(4,5) == ([(4,0), (5, len(c4))], c4 + c5)
        assert b.get_chunks(3,5) == ([(3,0), (4, len(c3)), (5, len(c3) + len(c4))], c3 + c4 + c5)


    def test_get_chunks_special_marks(self):
        b = cs.Buffer()

        c1 = secrets.token_bytes(math.floor(b.capacity / 3) - 1)
        c2 = secrets.token_bytes(math.floor(b.capacity / 3) - 2)
        c3 = secrets.token_bytes(math.floor(b.capacity / 3) - 3)
        c4 = secrets.token_bytes(math.floor(b.capacity / 3) - 4)

        # One item
        assert b.append_chunk(c1) == 1

        assert b.get_chunks(0, 1) == ([(1, 0)], c1)
        assert b.get_chunks(1, 0xffffffff) == ([(1, 0)], c1)
        assert b.get_chunks(0, 0xffffffff) == ([(1, 0)], c1)

        # Two items
        assert b.append_chunk(c2) == 2

        assert b.get_chunks(0,1) == ([(1, 0)], c1)
        assert b.get_chunks(0,2) == ([(1,0), (2, len(c1))], c1 + c2)
        assert b.get_chunks(2,0xffffffff) == ([(2, 0)], c2)
        assert b.get_chunks(1,0xffffffff) == ([(1,0), (2, len(c1))], c1 + c2)
        assert b.get_chunks(0,0xffffffff) == ([(1,0), (2, len(c1))], c1 + c2)

        # Wrap around
        assert b.append_chunk(c3) == 3
        assert b.append_chunk(c4) == 4

        assert b.get_chunks(0,2) == ([(2, 0)], c2)
        assert b.get_chunks(4,0xffffffff) == ([(4, 0)], c4)
        assert b.get_chunks(0,3) == ([(2,0), (3, len(c2))], c2 + c3)
        assert b.get_chunks(3,0xffffffff) == ([(3,0), (4, len(c3))], c3 + c4)
        assert b.get_chunks(0,0xffffffff) == ([(2,0), (3, len(c2)), (4, len(c2) + len(c3))], c2 + c3 + c4)

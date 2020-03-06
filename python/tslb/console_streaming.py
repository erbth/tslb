"""
A module that incoroprates functionality for streaming console output to a
client. I.e. to view the output of build commands on a build node from remote.
"""

from bisect import bisect_left
import array
import asyncio
import fcntl
import math
import os
import pty
import struct
import termios


class FDWrapper(object):
    def __init__(self, fd):
        self._fd = fd

    def fileno(self):
        return self._fd

    def close(self):
        os.close(self._fd)


def split_into_chunks(data, max_chunk_size=524288):
    """
    Split data into chunks based on certain criteria.

    :param bytes data: Data to split into chunks.
    :param int max_chunk_size: The maximum size of a chunk. Defaults to
        512 KiB.
    :returns List(bytes): The list of chunks created.
    """
    l = []

    i = 0
    size = len(data)

    while size - i > max_chunk_size:
        l.append(data[i:i + max_chunk_size])
        i += max_chunk_size

    l.append(data[i:])

    return l


class Buffer(object):
    """
    A ring buffer implementation for buffering console output in form of
    chunks.

    :param int capacity: The capacity for the data (!) buffer. Note that the
        metadata buffer can be ~ 10 times as large. Defaults to 10 MiB.
    """
    def __init__(self, capacity=10 * 1024 * 1024):
        self.capacity = capacity

        # Invariant: Data buffer has one free field between end and start (or
        # the array's end)
        self.data = bytearray(capacity)
        self.dend = 0

        # This invariant is not required for metadata buffers.
        self.mdmarks = array.array('L', [0])
        self.mdpointers = array.array('L', [0])
        self.mdstart = None
        self.mdend = None


    @property
    def empty(self):
        return self.mdstart == None


    @property
    def size(self):
        if self.mdstart == None:
            return 0

        else:
            start = self.mdpointers[self.mdstart]
            end = self.dend

            if start <= end:
                return end - start
            else:
                return self.capacity - start + end


    @property
    def first_mark(self):
        """
        The first (oldest) mark stored in the buffer or None if the buffer is
        empty.
        """
        if self.empty:
            return None

        return self.mdmarks[self.mdstart]


    @property
    def last_mark(self):
        """
        The last (newest) mark stored in the buffer or None if the buffer is
        empty.
        """
        if self.empty:
            return None

        return self.mdmarks[self.mdend]


    def append_chunk(self, data: bytes) -> int:
        """
        Append data as a chunk to the buffer

        :returns: The newly allocated mark
        :raises ValueError: If the data size is larger than the buffer size - 1
        """
        previous_last_mark = self.last_mark

        # Make space if required
        l = len(data)

        if l > self.capacity - 1:
            raise ValueError("Data chunk too large for buffer")

        while self.capacity - self.size <= l:
            if self.mdstart != self.mdend:
                self.mdstart = (self.mdstart + 1) % len(self.mdmarks)

            else:
                self.mdstart == None
                self.mdend == None
                self.dend == 0

        # Allocate a mark
        if previous_last_mark is not None:
            mark = previous_last_mark + 1

            if mark > 0xfffffffe:
                mark = 1

        else:
            mark = 1

        # Copy data
        start = self.dend
        end = (self.dend + l) % self.capacity

        if start <= end:
            self.data[start:end] = data
        else:
            self.data[start:] = data[0:self.capacity - start]
            self.data[0:end] = data[self.capacity - start:]

        self.dend = end

        # Update metadata
        md_count = (self.mdend - self.mdstart + 1) if self.mdstart is not None else 0

        if len(self.mdmarks) - md_count == 0:
            new_len = math.ceil(len(self.mdmarks) * 1.5)

            new_marks = array.array('L', range(new_len))
            new_pointers = array.array('L', range(new_len))

            if self.mdstart <= self.mdend:
                new_marks[0:md_count] = self.mdmarks[self.mdstart:self.mdend + 1]
                new_pointers[0:md_count] = self.mdpointers[self.mdstart:self.mdend + 1]

            else:
                eax = len(self.mdmarks) - self.mdstart

                new_marks[0:eax] = self.mdmarks[self.mdstart:]
                new_marks[eax:md_count] = self.mdmarks[0:self.mdend + 1]

                new_pointers[0:eax] = self.mdpointers[self.mdstart:]
                new_pointers[eax:md_count] = self.mdpointers[0:self.mdend + 1]

            self.mdmarks = new_marks
            self.mdpointers = new_pointers

            self.mdstart = 0
            self.mdend = md_count - 1


        if self.mdstart is None:
            self.mdmarks[0] = mark
            self.mdpointers[0] = start
            self.mdstart = 0
            self.mdend = 0

        else:
            self.mdend = (self.mdend + 1) % len(self.mdmarks)
            self.mdmarks[self.mdend] = mark
            self.mdpointers[self.mdend] = start

        return mark


    def _find_mark_index(self, mark):
        """
        Find the index of the given mark.

        :param int mark: The mark to find
        :returns: The index or None.
        """
        if self.empty:
            return None

        class array_proxy(object):
            def __init__(self, foreign):
                self.mdmarks = foreign.mdmarks
                self.mdstart = foreign.mdstart
                self.mdend = foreign.mdend


            def __getitem__(self, i):
                return self.mdmarks[(self.mdstart + i) % len(self.mdmarks)]


            def __len__(self):
                if self.mdstart <= self.mdend:
                    return self.mdend - self.mdstart + 1
                else:
                    return len(self.mdmarks) - self.mdstart + self.mdend + 1


        i = bisect_left(array_proxy(self), mark)

        if i != len(self.mdmarks):
            i = (self.mdstart + i) % len(self.mdmarks)
            if self.mdmarks[i] == mark:
                return i

        return None


    def get_chunk(self, mark):
        """
        Finds the chunk matching the given mark.

        :param int mark: The requested mark
        :returns: The chunk or None
        :rtype: bytearray or NoneType

        :raises ValueError: If mark is <= 0 of >= 0xFFFFFFFF
        """
        if mark <= 0 or mark >= 0xffffffff:
            raise ValueError("marks -infinity and now not allowed.")

        i = self._find_mark_index(mark)
        if i is None:
            return None

        start = self.mdpointers[i]
        end = self.mdpointers[(i+1) % len(self.mdpointers)] if i != self.mdend else self.dend

        if start <= end:
            return self.data[start:end]
        else:
            return self.data[start:] + self.data[:end]


    def get_chunks(self, mstart, mend):
        """
        Finds the chunks between mstart and mend. mstart maybe 0 (interpreted
        as minus infinity) or 0xFFFFFFFF (interpreted as last value / now).

        mstart must be smaller than mend with respect to rollover properties.

        :param int mstart: The first mark of the range to return
        :param int mend: The last mark of the range to return
        :returns: A tuple(ordered_list(marks*pointers), data)
        :rtype: Tuple(List(Tuple(int,int)), bytearray)
        :raises ValueError: If mstart / mend are not in the buffer, or mstart >
            mend with respect to rollover properties.
        """
        if mstart == 0:
            istart = self.mdstart
        else:
            istart = self._find_mark_index(mstart)
            if istart is None:
                raise ValueError("mstart not in the buffer.")

        if mend == 0xffffffff:
            iend = self.mdend
        else:
            iend = self._find_mark_index(mend)
            if iend is None:
                raise ValueError("mend not in the buffer.")


        if self.mdstart <= self.mdend:
            if istart > iend:
                raise ValueError("mstart > mend (1)")

        else:
            if istart >= self.mdstart and iend >= self.mdstart and iend < istart:
                raise ValueError("mstart > mend (2)")

            elif istart <= self.mdend and iend <= self.mdend and iend < istart:
                raise ValueError("mstart > mend (3)")

            elif iend >= self.mdstart and istart <= self.mdend:
                raise ValueError("mstart > mend (4)")


        start = self.mdpointers[istart]
        end = self.mdpointers[(iend+1) % len(self.mdpointers)] if iend != self.mdend else self.dend

        m = []
        i = None
        while i != iend:
            if i is None:
                i = istart
            else:
                i = (i + 1) % len(self.mdmarks)

            p = self.mdpointers[i]
            if p >= start:
                p -= start
            else:
                p = p + self.capacity - start

            m.append((self.mdmarks[i], p))

        if start <= end:
            return (m, self.data[start:end])
        else:
            return (m, self.data[start:] + self.data[:end])


class ConsoleAccessProtocol(object):
    """
    Abstrace base class for console access protocol (cas) implementations.

    The only requirement on addresses is that they are (easily) comparable,
    have a proper hash function and are unique among all clients.

    Splitting sent data / updates into chunks suitable to be transfered through
    the communication channel / sent as a datagram is left to the protocol
    implementation. But note that not more than the buffer size + mdata size
    will ever be transfered (obviously there's not more data to play with).

    Upon registration the streamer will fill out the receiver to streamer
    methods.
    """
    def updates_requested(self, addr):
        """
        Receiver to streamer

        Called by the protocol implementation if a request_updates message is
        received from a client with unique address.
        """
        raise NotImplemented


    def update_acknowledged(self, addr):
        """
        Receiver to streamer

        Called by the protocol implementation if an ACK is received from a
        client with unique address.
        """
        raise NotImplemented


    def requested(self, addr, start, end):
        """
        Receiver to streamer

        Called by the protocol implementation if a request message is received
        from a client with unique address. start and end are 32 bit unsigned
        integers (just stay in that range) for start and end mark.
        """
        raise NotImplemented


    def input(self, addr, data):
        """
        Receiver to streamer

        Called by the protocol implementation if an input mesage is received
        from a client with unique address.
        """
        raise NotImplemented


    def data(self, addr, mdata, data):
        """
        Streamer to receiver

        :param addr: Unique address
        :param mdata: list(marks*pointers)
        :type mdata: List(Tuple(int, int))
        :param bytes data: binary buffer
        """
        raise NotImplemented


    def update(self, addr, mdata, data):
        """
        Streamer to receiver

        :param addr: Unique address
        :param mdata: list(marks*pointers)
        :type mdata: List(Tuple(int, int))
        :param bytes data: binary buffer
        """
        raise NotImplemented


class ConsoleStreamer(object):
    """
    The actual console streamer.

    :param ClientAccessProtocol cas: The client access protocol implementation
        to use.
    """
    def __init__(self, cas):
        self.buffer = Buffer()
        self.pty_master, self.pty_slave = pty.openpty()

        fcntl.ioctl(self.pty_slave, termios.TIOCSWINSZ,
                struct.pack("HHHH", 25, 80, 0, 0))

        self.subscribers = []

        # Register protocol
        cas.updates_requested = self.updates_requested
        cas.update_acknowledged = self.update_acknowledged
        cas.requested = self.requested
        cas.input = self.input

        self.send_data = cas.data
        self.send_update = cas.update

        loop = asyncio.get_running_loop()
        self._start_task = loop.create_task(self._start())
        self._timer_task = None
        self._pty_transport = None


    def __del__(self):
        self.stop_tasks


    def stop_tasks(self):
        if self._start_task:
            self._start_task.cancel()

        if self._timer_task is not None:
            self._timer_task.cancel()


    def updates_requested(self, addr):
        """
        AKA subscribe
        """
        if addr not in [a for a,s in self.subscribers]:
            self.subscribers.append((addr, 0))


    def update_acknowledged(self, addr):
        for i,t in enumerate(self.subscribers):
            a,_ = t
            if a == addr:
                self.subscribers[i] = (a, 0)
                break


    def input(self, blob):
        os.write(self.pty_master, blob)


    def requested(self, addr, start, end):
        # Empty buffer case
        if self.buffer.empty:
            self.send_data(addr, [], b'')
            return

        # Bound input
        if self.buffer.first_mark <= self.buffer.last_mark:
            if start != 0:
                start = max(start, self.buffer.first_mark)
                start = min(start, self.buffer.last_mark)

            if end != 0xffffffff:
                end = max(end, self.buffer.first_mark)
                end = min(end, self.buffer.last_mark)

            if end < start:
                end = start


        else:
            if start != 0:
                if start < self.buffer.first_mark and start > self.buffer.last_mark:
                    start = self.buffer.first_mark

            if end != 0xffffffff:
                if end < self.buffer.first_mark and end > self.buffer.last_mark:
                    end = self.buffer.first_mark

            if (start >= self.buffer.first_mark and end >= self.buffer.first_mark) or\
                    (start <= self.buffer.last_mark and end <= self.buffer.last_mark):
                if end < start:
                    end = start

            elif start <= self.buffer.last_mark and end >= self.buffer.first_mark:
                end = start

        mdata, blob = self.buffer.get_chunks(start, end)
        self.send_data(addr, mdata, blob)


    def append_chunks(self, chunks):
        mdata = []
        pointer = 0
        
        for c in chunks:
            mark = self.buffer.append_chunk(c)
            mdata.append((mark, pointer))
            pointer += len(c)

        # Update subscribers
        if self.subscribers:
            blob = b''.join(chunks)

            for i,t in enumerate(self.subscribers):
                addr, state = t

                self.send_update(addr, mdata, blob)

                self.subscribers[i] = (addr, 1 if state == 0 else state)


    async def _start(self):
        """
        Main worker coroutine to process incomming data (console output)
        """
        loop = asyncio.get_running_loop()

        # Register a clock timer
        async def _timer(self):
            while True:
                await asyncio.sleep(1)
                self.clk()

        self._timer_task = loop.create_task(_timer(self))

        # Set PTY reader
        class PTYProtocol(asyncio.Protocol):
            @staticmethod
            def data_received(data):
                chunks = split_into_chunks(data)
                self.append_chunks(chunks)

        self._pty_transport, _ = await loop.connect_read_pipe(
            PTYProtocol, FDWrapper(self.pty_master))


    def clk(self):
        """
        Called once per second
        """
        i = 0

        while i < len(self.subscribers):
            addr, state = self.subscribers[i]

            if state == 0:
                i += 1
            elif state == 1:
                self.subscribers[i] = (addr, state + 1)
                i += 1
            else:
                del self.subscribers[i]

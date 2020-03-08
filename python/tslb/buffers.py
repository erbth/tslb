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
import threading


class ConsoleBufferFixedSize(object):
    """
    A ring buffer implementation for buffering console output with fixed size.
    This class if fully thread safe. But be aware that data may change from
    call to call if multiple tasks use one buffer ...
    Of course you can lock the datastructure manually for this. But if you like
    to try that you probably know it is possible anyway ...

    :param int capacity: The capacity for the buffer.
    :raises ValueError: If capacity is < 0
    """
    def __init__(self, capacity=10 * 1024 * 1024):
        if capacity < 0:
            raise ValueError("A capacity must by >= 0.")

        self._buf_capacity = capacity + 1

        # Invariant: Data buffer has one free field between end and start (or
        # the array's end)
        self.data = bytearray(self._buf_capacity)
        self.begin = 0
        self.end = 0

        self.lk = threading.RLock()


    @property
    def empty(self):
        with self.lk:
            return self.begin == self.end


    @property
    def capacity(self):
        with self.lk:
            return self._buf_capacity - 1


    @property
    def size(self):
        with self.lk:
            if self.begin <= self.end:
                return self.end - self.begin
            else:
                return self._buf_capacity - self.begin + self.end


    @property
    def free(self):
        with self.lk:
            return self._buf_capacity - self.size - 1


    def append_data(self, data: bytes):
        """
        Append data to the buffer

        :raises ValueError: If the data size is larger than the buffer size - 1
        """
        with self.lk:
            # Make space if required
            l = len(data)

            if l > self._buf_capacity - 1:
                raise ValueError("Data too large for buffer.")

            to_free = max(0, l - self.free)

            self.begin = (self.begin + to_free) % self._buf_capacity


            # Copy data
            if self.end + l < self._buf_capacity:
                self.data[self.end:self.end + l] = data
                self.end += l

            else:
                self.data[self.end:] = data[0:self._buf_capacity - self.end]
                self.data[0:l - (self._buf_capacity - self.end)] = data[self._buf_capacity - self.end:]
                self.end = l - (self._buf_capacity - self.end)


    def read_data(self, amount: int) -> bytearray:
        """
        Read data from the buffer. In particular this reads from the given
        amount of data back to the current front end. It behaves like tail. The
        amount given maybe -1 in which case all stored data is returned. If the
        given amount is bigger than the actual size of the stored data, the
        entire data is returned.
        """
        with self.lk:
            if amount < 0:
                to_read = self.size

            else:
                to_read = min(self.size, amount)

            p1 = self.data[max(0, self.end - to_read):self.end]

            if len(p1) < to_read:
                p2 = self.data[self._buf_capacity - (to_read - len(p1)):self._buf_capacity]
                return p2 + p1

            else:
                return p1


    def clear(self):
        """
        Clears all content.
        """
        with self.lk:
            self.begin = 0
            self.end = 0

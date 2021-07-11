"""
Basic utils like checking if a mountpoint is mounted that do not require extra
functionality from TSLB. Putting them in an extra module avoids cyclic imports
by the higher-level functionality from utils.py, which requires other parts of
the TSLB which in turn require these basic utils.
"""
import contextlib
import io
import os
import pty
import select
import sys
import threading
import traceback


class FDWrapper:
    """
    Wraps an fd into something that behaves like sys.stdout etc.
    This does NOT close the fd on deletion!

    :param int fd: The fd to wrap
    """
    def __init__(self, fd):
        self._fd = fd

    def fileno(self):
        return self._fd

    def close(self):
        os.close(self._fd)


    def write(self, data):
        """
        :type data: str or bytes
        """
        if isinstance(data, str):
            data = data.encode('utf8')

        os.write(self._fd, data)


def is_mounted(path):
    """
    Returns true if the specified path exists and something is mounted there
    i.e. it is a mountpoint.
    """
    with open('/proc/mounts', 'r', encoding='UTF-8') as f:
        for mountpoint in f:
            if mountpoint.split()[1] == path:
                return True

    return False


class LogTransformer:
    """
    A context manager that provides the writer-end of a pty in from of an
    sys.stdout-like object and starts a background thread which reads from it,
    transforms log lines accordingly and writes the output to the given
    stdout-like object.

    It can optionally aquire a given lock while writing to protect the output
    FD.

    :param str pattern: Pattern used when writing to the output. %(line)s is
                        substituted by a line read from the input.
    :param out:         Output sys.stdout-like object
    :param lock:        Optional lock to acquire while writing, defaults to
                        None.
    """
    def __init__(self, pattern, out, lock=None):
        self._pattern = pattern
        self._out = out
        self._lock = lock
        self._master = None
        self._slave = None
        self._worker = None

        self._pipe_r = None
        self._pipe_w = None

    def _worker_fun(self):
        while True:
            rfds,_,_ = select.select([self._master, self._pipe_r], [], [])
            if self._master in rfds:
                lines = os.read(self._master, 65535)
            elif self._pipe_r in rfds:
                break

            # read() returning zero indicates EOF
            if not lines:
                return

            lines = lines.decode('utf8').replace('\r', '').rstrip('\n').split('\n')
            text = ''.join((self._pattern % {'line': line}) + '\n' for line in lines)

            if self._lock is not None:
                with self._lock:
                    self._out.write(text)
            else:
                self._out.write(text)

    def __enter__(self):
        self._master, self._slave = pty.openpty()
        self._pipe_r, self._pipe_w = os.pipe()
        self._worker = threading.Thread(target=self._worker_fun)
        self._worker.start()
        return FDWrapper(self._slave)

    def __exit__(self, exc_type, exc_value, traceback):
        # Request exit
        os.write(self._pipe_w, b'1')
        self._worker.join()

        os.close(self._slave)
        os.close(self._master)
        os.close(self._pipe_r)
        os.close(self._pipe_w)

        self._master = None
        self._slave = None
        self._pipe_r = None
        self._pipe_w = None
        self._worker = None


@contextlib.contextmanager
def thread_inspector(stop=True):
    """
    Start a thread inspecing all threads to e.g. find deadlocks.

    :param bool stop: Stop the monitor after exiting the with-statement
        (defaults to True, may interfer with other things if kept running...)
    """
    ev = threading.Event()

    def debug_fcnt():
        while True:
            if ev.wait(1):
                break

            # Print all threads
            print("Threads: (PID: %s)" % os.getpid())
            frames = sys._current_frames()
            for t in threading.enumerate():
                frame = frames.get(t.ident)
                if not frame:
                    continue

                c = frame.f_code
                pos = c.co_filename + ":" + str(frame.f_lineno)
                print("  %s (%s): %s" % (t.ident, t.name, pos))
                print(traceback.print_stack(frame))

    thdbg = threading.Thread(target=debug_fcnt)
    thdbg.start()

    yield

    if stop:
        ev.set()
        thdbg.join()


def replace_output_streams():
    """
    Replace sys.stdout and sys.stderr with new TextIOWrappers wrapping fds 1
    and 2 respectively. This can be useful when the original
    sys.stdout/sys.stderr is locked forever e.g. after a fork, where the child
    process does not contain a thread from the parent process that locked them
    and hence cannot unlock the streams.
    """
    sys.stdout = io.TextIOWrapper(
            buffer=io.BufferedWriter(
                raw=io.FileIO(1, mode='wb', closefd=False)
            ),
            encoding='utf8')

    sys.stderr = io.TextIOWrapper(
            buffer=io.BufferedWriter(
                raw=io.FileIO(2, mode='wb', closefd=False)
            ),
            encoding='utf8')


def read_file(filename, encoding=None, fallback=None):
    """
    Read a file and return its content. If :param encoding: is given, the file
    is read in text mode using the given encoding and a str is returned.
    Otherwise it's read in binary mode and bytes are returned.

    If :param encoding: is 'system', the system's default encoding is used.

    :param fallback: If not None, this encoding will be used in case the
        primary encoding raises an error.
    """
    with open(filename, 'rb') as f:
        content = f.read()

        try:
            if encoding == 'system':
                return content.decode()
            elif encoding:
                return content.decode(encoding)
            else:
                return content

        except UnicodeDecodeError:
            if fallback:
                return content.decode(fallback)
            else:
                raise

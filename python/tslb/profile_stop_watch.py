import sys
import threading
import time
from tslb import Console

all_watches_lock = threading.RLock()
all_watches = []

class Interval:
    """
    An interval [begin, end)
    """
    def __init__(self, begin, end):
        self.begin = begin
        self.end = end

    @property
    def delta(self):
        return self.end - self.begin

class ProfileStopWatch:
    def __init__(self, name):
        self.name = name
        self.lock = threading.RLock()

        with self.lock:
            self.start_time = None
            self.intervals = []

            with all_watches_lock:
                all_watches.append(self)

    def start(self):
        with self.lock:
            if self.start_time is not None:
                raise RuntimeError("ProfileStopWatch `%s' already running." % self.name)

            self.start_time = time.clock_gettime(time.CLOCK_MONOTONIC)

    def stop(self):
        with self.lock:
            if self.start_time is None:
                raise RuntimeError("ProfileStopWatch `%s' not running." % self.name)

            self.intervals.append(Interval(self.start_time, time.clock_gettime(time.CLOCK_MONOTONIC)))
            self.start_time = None

    @property
    def total_time(self):
        with self.lock:
            if self.start_time:
                raise RuntimeError("ProfileStopWatch `%s' running; can't compute total time.")

            return sum([i.delta for i in self.intervals])


def print_all(file=sys.stdout):
    """
    Print all stop watches and their total elapsed times.
    """
    watches = sorted([(w.name, w.total_time) for w in all_watches])
    cnt = max(len(t[0]) for t in watches)

    print("All watches:", file=file)
    Console.print_horizontal_bar(file=file)

    for name, _time in watches:
        print("  `%*s': %fs" % (cnt, name, _time), file=file)
